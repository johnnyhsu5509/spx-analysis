"""每日一鍵：讀一份合併敘事 JSON，依序跑記帳腳本與 HTML 渲染器。

  python scripts/daily_run.py --symbol spx --docs docs --today scripts/today_data.txt --narrative narrative_MMDD.json [--out DIR]
  python scripts/daily_run.py --symbol ndx --docs docs --today scripts/ndx_today_data.txt --aux ndx_aux.json --narrative narrative_MMDD.json [--out DIR]

不加 --out 只寫 --report，不寫帳本與 HTML。--out 指向 docs 才是正式寫入（含 docs/spx|ndx/index.html，從不碰 docs/index.html）。
NDX 的 SPX 對照預設讀 --out 裡的 last_analysis.json（影子模式），沒有就讀 --docs 的；可用 --spx-last 指定。
版型沿用 --docs 裡最近一份同系統報告，可用 --head-from 指定。
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
from mech_lib import ld, sv


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
    tag = day.replace('-', '')
    head = render_spx_html.head_from(a.head_from or latest_report(a.docs, a.symbol, tag), day)
    page = render(ledgers, td, nar, head)
    name = f'{a.symbol}-analysis-{tag}.html'
    report.update(html=name, html_bytes=len(page.encode('utf-8')), wrote=a.out)
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
    p.add_argument('--report', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'daily_run_report.txt'))
    return run(p.parse_args(argv))


if __name__ == '__main__':
    main()
