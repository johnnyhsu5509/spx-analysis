"""Phase 3 修正欄位（2026-11-04）＋方案 G（2026-11-10）：部位水位 position_level、現有持股動作 holding_action、
振幅命中率 amp_hit_rate、事件日 event_day、頂端摘要行 summary_line。

給「模型手寫報告」的路徑用；daily_run 流水線已內建 Phase 3 的同一套（共用 mech_lib 的函式），holding_action 尚未接上流水線。

  python3 scripts/phase3_fields.py --symbol spx --docs docs --today scripts/today_data.txt [--ndx-today 檔 ...] [--event-day yes|no --event-note 說明] [--apply] [--html 報告.html ...]
  python3 scripts/phase3_fields.py --symbol ndx --docs docs --today scripts/ndx_today_data.txt [--event-day yes|no --event-note 說明] [--apply] [--html 報告.html ...]

不加 --apply 只算、寫 --report，不改任何帳本或 HTML。--html 只在有 --apply 時寫入：頁面最上方放「現有持股動作＋摘要」區塊（可重複執行、原地取代）；
SPX 另在 <footer> 前放「部位水位」區塊（NDX 的報告模板本來就有）。
水位判定式不變（prc-014：close > MA200 → 正常，否則半倉）；切換或半倉不再停下，改由 holding_action 寫出動作，切換日在 --apply 時補寫 position_gate.events。
這一籃（科技／NDX／QQQ／半導體）一律看 NDX 閘門：SPX 報告優先用 docs/ndx_last_analysis.json（基準日相符），
其次用 --ndx-today 檔（預設 scripts/ndx_today_data.txt、data/ndx_today_data.txt）重算，都沒有就沿用前一日水位並註明資料落後。
today_data 的 trade_date 必須等於 last_analysis 的資料基準日，否則停下。方向（direction）不會被改動。
"""
import argparse
import os

from mech_lib import (add_switch_event, amp_hit_rate, holding_action, inject_banner, inject_position, ld, position_html, position_state,
                      seed_position, semis_for, semis_ref, summary_line, sv)
from mech_lib import ndx_gate as ndx_gate_core

SYM = {'spx': {'name': 'SPX', 'last': 'last_analysis.json', 'track': 'track_record.json'},
       'ndx': {'name': 'NDX', 'last': 'ndx_last_analysis.json', 'track': 'ndx_track_record.json'}}
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NDX_TD = (os.path.join(REPO, 'scripts', 'ndx_today_data.txt'), os.path.join(REPO, 'data', 'ndx_today_data.txt'))


def ndx_gate(docs, day, td_files):
    """讀檔後交給 mech_lib.ndx_gate（daily_run 用同一段）。"""
    p = os.path.join(docs, SYM['ndx']['last'])
    old = (ld(p) if os.path.exists(p) else {}).get('position_level')
    return ndx_gate_core(old, day, [ld(f) for f in td_files if os.path.exists(f)])


def build(symbol, docs, td, event_day=None, event_note='', ndx_td_files=NDX_TD):
    cfg = SYM[symbol]
    la, tr = ld(os.path.join(docs, cfg['last'])), ld(os.path.join(docs, cfg['track']))
    day = td['trade_date']
    if la['data_basis'][:10] != day:
        raise SystemExit(f"today_data 的 trade_date {day} 不是 {cfg['last']} 的資料基準日 {la['data_basis']}")
    if la['direction']['prob'] != 50:
        raise SystemExit('direction 不是 50：本腳本只涵蓋 Phase 3 方向恆 50')
    old = la.get('position_level') or seed_position(tr)
    if old is None:
        raise SystemExit(f"{cfg['last']} 沒有 position_level，{cfg['track']} 也沒有 position_gate.events：先登記 rule59 的起算日")
    la['position_level'] = position_state(old, td['close'], td['ma200'], day)
    la['amp_hit_rate'] = amp_hit_rate(tr['amp_track']['entries'])
    if event_day is not None:
        la['event_day'] = {'is_event_day': event_day, 'note': event_note}
    else:
        la.setdefault('event_day', {'is_event_day': None, 'note': ''})
    g, note = (la['position_level'], '') if symbol == 'ndx' else ndx_gate(docs, day, ndx_td_files)
    ha = holding_action(g, la['trade_date'], note)
    alts = [] if symbol == 'ndx' else [ld(f) for f in ndx_td_files if os.path.exists(f)]
    ha['semis_ref'] = semis_ref(semis_for(td, alts))
    la['holding_action'] = ha
    la['summary_line'] = summary_line(cfg['name'], la, la['position_level'])
    return la


def patch_html(symbol, path, la):
    with open(path, encoding='utf-8', newline='') as f:
        page = f.read()
    page = inject_banner(page, la)
    if symbol == 'spx':
        page = inject_position(page, position_html('SPX', la['position_level']))
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(page)


def record_switch(docs, symbol, pl):
    """切換日補寫 position_gate.events（同一訊號日不重複寫）。"""
    p = os.path.join(docs, SYM[symbol]['track'])
    tr = ld(p)
    if add_switch_event(tr, pl, SYM[symbol]['name']):
        sv(p, tr)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', choices=tuple(SYM), required=True)
    p.add_argument('--docs', required=True)
    p.add_argument('--today', required=True)
    p.add_argument('--ndx-today', nargs='*', default=list(NDX_TD))
    p.add_argument('--event-day', choices=('yes', 'no'))
    p.add_argument('--event-note', default='')
    p.add_argument('--apply', action='store_true')
    p.add_argument('--html', nargs='*', default=[])
    p.add_argument('--report', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'phase3_fields_report.txt'))
    a = p.parse_args(argv)
    ev = None if a.event_day is None else a.event_day == 'yes'
    la = build(a.symbol, a.docs, ld(a.today), ev, a.event_note, a.ndx_today)
    if a.apply:
        sv(os.path.join(a.docs, SYM[a.symbol]['last']), la)
        if la['position_level']['switched_today']:
            record_switch(a.docs, a.symbol, la['position_level'])
        for h in a.html:
            patch_html(a.symbol, h, la)
    sv(a.report, {'symbol': a.symbol, 'applied': a.apply, 'html': a.html if a.apply else [], 'holding_action': la['holding_action'],
                  'summary_line': la['summary_line'], 'position_level': la['position_level'], 'amp_hit_rate': la['amp_hit_rate'],
                  'event_day': la['event_day']})
    return la


if __name__ == '__main__':
    main()
