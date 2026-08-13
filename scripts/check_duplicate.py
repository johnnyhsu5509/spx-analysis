# -*- coding: utf-8 -*-
"""重複分析防護：比對本次收盤是否已被分析過。ASCII-only output (cp950 safe)."""
import json, io, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BASE)
def load(p):
    try:
        return json.load(io.open(p, encoding='utf-8'))
    except Exception as e:
        return {'__error__': repr(e)}

td = load(os.path.join(BASE, 'today_data.txt'))
la = load(os.path.join(REPO, 'docs', 'last_analysis.json'))
tr = load(os.path.join(REPO, 'docs', 'track_record.json'))
pl = load(os.path.join(REPO, 'docs', 'pnl_ledger.json'))

trade_date = td.get('trade_date')
data_basis = la.get('data_basis', '')
report_date = la.get('trade_date')

dup_basis = bool(trade_date) and trade_date in str(data_basis)

# 三本帳是否已有以本收盤為基準的 entry
tr_dates = [e.get('report_date') for e in tr.get('entries', []) if isinstance(e, dict)]
pl_dates = [e.get('report_date') for e in pl.get('entries', []) if isinstance(e, dict)]
tr_pending = [e.get('report_date') for e in tr.get('entries', [])
              if isinstance(e, dict) and e.get('grade') == 'pending']

no_data = (not trade_date) or ('__error__' in td)
verdict = 'NO_DATA' if no_data else ('DUPLICATE' if dup_basis else 'OK')

lines = [
    'VERDICT: %s' % verdict,
    'today_data.trade_date      : %s' % trade_date,
    'last_analysis.data_basis   : %s' % data_basis,
    'last_analysis.report_date  : %s' % report_date,
    'track_record last 3        : %s' % ', '.join(map(str, tr_dates[-3:])),
    'pnl_ledger last 3          : %s' % ', '.join(map(str, pl_dates[-3:])),
    'track_record pending       : %s' % ', '.join(map(str, tr_pending)),
    '',
]
if no_data:
    lines += [
        'MEANING: today_data.txt is empty/unreadable -> the fetch FAILED.',
        'ACTION : STOP. Do NOT analyze. Re-run fetch_today.py and read its error.',
        '         Likely cause: egress allowlist missing one of',
        '         query1.finance.yahoo.com / query2.finance.yahoo.com / fc.yahoo.com',
        'NEVER  : run the analysis on stale or empty data.',
    ]
elif dup_basis:
    lines += [
        'MEANING: this US close has ALREADY been analyzed.',
        'ACTION : STOP. Do not append to the three ledgers.',
        '         Ask the user: (a) show previous result only  [default]',
        '                       (b) rerun and REPLACE same-date entries',
        '                       (c) cancel',
        'NEVER  : append a second entry for the same report_date.',
    ]
else:
    lines += ['MEANING: new close detected, safe to run full analysis.']

out = '\n'.join(lines)
io.open(os.path.join(BASE, 'dup_check.txt'), 'w', encoding='utf-8', newline='\n').write(out + '\n')
print(out)
sys.exit(0)
