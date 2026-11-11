"""每日一鍵：讀一份合併敘事 JSON，依序跑記帳腳本與 HTML 渲染器。

  python scripts/daily_run.py --symbol spx --docs docs --today scripts/today_data.txt --narrative narrative_MMDD.json [--out DIR]
  python scripts/daily_run.py --symbol ndx --docs docs --today scripts/ndx_today_data.txt --aux ndx_aux.json --narrative narrative_MMDD.json [--out DIR]

不加 --out 只寫 --report，不寫帳本與 HTML。--out 指向 docs 才是正式寫入（含 docs/spx|ndx/index.html，從不碰 docs/index.html）。
NDX 的 SPX 對照預設讀 --out 裡的 last_analysis.json（影子模式），沒有就讀 --docs 的；可用 --spx-last 指定。
版型沿用 --docs 裡最近一份同系統報告，可用 --head-from 指定。

方案 G（2026-11-10）：報告第一句＝對現有科技／NDX／QQQ／半導體持股的動作（維持／加碼／減碼＋目標 %），寫進 last_analysis 的
holding_action 與 rating 開頭，HTML 頁首依序為 動作句 → 新增多單 → 半導體參考 → 摘要行。這一籃一律看 NDX 閘門：NDX 報告用自己的
position_level；SPX 報告依序用 --docs 的 ndx_last_analysis.json（基準日相符）→ --ndx-today 檔（預設 scripts／data 的 ndx_today_data.txt）→
沿用前一日水位並註明資料落後。水位判定式不變（prc-014）；切換或半倉不停下，切換日補寫 position_gate.events。
"""
import argparse
import glob
import os
import re

import ndx_daily_mech
import ndx_last_mech
import render_ndx_html
import render_spx_html
import spx_daily_mech
from mech_lib import add_switch_event, apply_holding, ld, ndx_gate, sv

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NDX_TD = (os.path.join(REPO, 'scripts', 'ndx_today_data.txt'), os.path.join(REPO, 'data', 'ndx_today_data.txt'))


def holding(a, ledgers, td):
    """寫第一句與切換事件（只動記憶體裡的 ledgers；是否落檔由 --out 決定）。"""
    last, track, name = (('last_analysis.json', 'track_record.json', 'SPX') if a.symbol == 'spx'
                         else ('ndx_last_analysis.json', 'ndx_track_record.json', 'NDX'))
    la = ledgers[last]
    pl = la['position_level']
    add_switch_event(ledgers[track], pl, name)
    alts = []
    if a.symbol == 'ndx':
        gate, note = pl, ''
    else:
        p = os.path.join(a.docs, 'ndx_last_analysis.json')
        old = (ld(p) if os.path.exists(p) else {}).get('position_level')
        files = NDX_TD if a.ndx_today is None else a.ndx_today
        alts = [ld(f) for f in files if os.path.exists(f)]
        gate, note = ndx_gate(old, td['trade_date'], alts)
    return apply_holding(la, gate, note, td, alts), pl['switched_today']


def latest_report(docs, symbol, before):
    tags = sorted(m.group(1) for f in glob.glob(os.path.join(docs, f'{symbol}-analysis-*.html'))
                  if (m := re.search(r'-(\d{8})\.html$', f)) and m.group(1) < before)
    if not tags:
        raise SystemExit(f'{docs} 找不到 {symbol}-analysis-*.html 可沿用版型，請用 --head-from 指定')
    return os.path.join(docs, f'{symbol}-analysis-{tags[-1]}.html')


def run(a):
    td, nar = ld(a.today), ld(a.narrative)
    if a.symbol == 'spx':
        ledgers, report = spx_daily_mech.build(a.docs, td, nar, a.report_date)
        report = {'mech': report}
        day = ledgers['last_analysis.json']['trade_date']
        render = render_spx_html.render
    else:
        if not a.aux:
            raise SystemExit('NDX 需要 --aux')
        ledgers, report = ndx_daily_mech.build(a.docs, td, nar, a.report_date)
        shadow = os.path.join(a.out, 'last_analysis.json') if a.out else ''
        spx = a.spx_last or (shadow if os.path.exists(shadow) else os.path.join(a.docs, 'last_analysis.json'))
        last, report2 = ndx_last_mech.build(a.docs, ledgers, td, ld(a.aux), ld(spx), nar, a.report_date)
        ledgers.update(last)
        report = {'mech': report, 'last': report2, 'spx_last': spx}
        day = last['ndx_last_analysis.json']['trade_date']
        render = render_ndx_html.render
    ha, switched = holding(a, ledgers, td)
    tag = day.replace('-', '')
    head = render_spx_html.head_from(a.head_from or latest_report(a.docs, a.symbol, tag), day)
    page = render(ledgers, td, nar, head)
    name = f'{a.symbol}-analysis-{tag}.html'
    report.update(html=name, html_bytes=len(page.encode('utf-8')), wrote=a.out, holding_action=ha['text'], new_long=ha['new_long'],
                  semis_ref=ha['semis_ref'], position_switched=switched)
    if a.out:
        os.makedirs(os.path.join(a.out, a.symbol), exist_ok=True)
        for f, o in ledgers.items():
            sv(os.path.join(a.out, f), o)
        for p in (os.path.join(a.out, name), os.path.join(a.out, a.symbol, 'index.html')):
            with open(p, 'w', encoding='utf-8', newline='\n') as f:
                f.write(page)
    sv(a.report, report)
    return report


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', choices=('spx', 'ndx'), required=True)
    for k in ('--docs', '--today', '--narrative'):
        p.add_argument(k, required=True)
    for k in ('--aux', '--spx-last', '--head-from', '--report-date', '--out'):
        p.add_argument(k)
    p.add_argument('--ndx-today', nargs='*', help='SPX 報告的 NDX 閘門備援資料檔（預設 scripts／data 的 ndx_today_data.txt）')
    p.add_argument('--report', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'daily_run_report.txt'))
    return run(p.parse_args(argv))


if __name__ == '__main__':
    main()
