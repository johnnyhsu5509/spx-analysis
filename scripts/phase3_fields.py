"""Phase 3 修正欄位（2026-11-04）：部位水位 position_level、振幅命中率 amp_hit_rate、事件日 event_day、頂端摘要行 summary_line。

給「模型手寫報告」的路徑用；daily_run 流水線已內建同一套（共用 mech_lib 的函式）。

  python3 scripts/phase3_fields.py --symbol spx --docs docs --today scripts/today_data.txt [--event-day yes|no --event-note 說明] [--apply] [--html 報告.html ...]
  python3 scripts/phase3_fields.py --symbol ndx --docs docs --today scripts/ndx_today_data.txt [--event-day yes|no --event-note 說明] [--apply] [--html 報告.html ...]

不加 --apply 只算、寫 --report，不改任何帳本或 HTML。--html 只在有 --apply 時寫入：頁面最上方放摘要區塊（可重複執行、原地取代）；
SPX 另在 <footer> 前放「部位水位」區塊（NDX 的報告模板本來就有）。
today_data 的 trade_date 必須等於 last_analysis 的資料基準日，否則停下。方向（direction）不會被改動。
"""
import argparse
import os

from mech_lib import amp_hit_rate, inject_banner, inject_position, ld, position_html, position_level, seed_position, summary_line, sv

SYM = {'spx': {'name': 'SPX', 'last': 'last_analysis.json', 'track': 'track_record.json'},
       'ndx': {'name': 'NDX', 'last': 'ndx_last_analysis.json', 'track': 'ndx_track_record.json'}}


def build(symbol, docs, td, event_day=None, event_note=''):
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
    la['position_level'] = position_level(old, td['close'], td['ma200'], day)
    la['amp_hit_rate'] = amp_hit_rate(tr['amp_track']['entries'])
    if event_day is not None:
        la['event_day'] = {'is_event_day': event_day, 'note': event_note}
    else:
        la.setdefault('event_day', {'is_event_day': None, 'note': ''})
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


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', choices=tuple(SYM), required=True)
    p.add_argument('--docs', required=True)
    p.add_argument('--today', required=True)
    p.add_argument('--event-day', choices=('yes', 'no'))
    p.add_argument('--event-note', default='')
    p.add_argument('--apply', action='store_true')
    p.add_argument('--html', nargs='*', default=[])
    p.add_argument('--report', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'phase3_fields_report.txt'))
    a = p.parse_args(argv)
    ev = None if a.event_day is None else a.event_day == 'yes'
    la = build(a.symbol, a.docs, ld(a.today), ev, a.event_note)
    if a.apply:
        sv(os.path.join(a.docs, SYM[a.symbol]['last']), la)
        for h in a.html:
            patch_html(a.symbol, h, la)
    sv(a.report, {'symbol': a.symbol, 'applied': a.apply, 'html': a.html if a.apply else [], 'summary_line': la['summary_line'],
                  'position_level': la['position_level'], 'amp_hit_rate': la['amp_hit_rate'], 'event_day': la['event_day']})
    return la


if __name__ == '__main__':
    main()
