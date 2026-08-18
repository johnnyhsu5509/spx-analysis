# -*- coding: utf-8 -*-
"""重複分析防護：比對本次收盤是否已被分析過。ASCII-only output (cp950 safe)."""
import json, io, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BASE)

# SPX 為預設；NDX 用 --symbol ndx。兩套帳本分離，各自防重複。
SYMBOLS = {
    'spx': {'data': 'today_data.txt', 'prefix': '', 'out': 'dup_check.txt'},
    'ndx': {'data': 'ndx_today_data.txt', 'prefix': 'ndx_', 'out': 'ndx_dup_check.txt'},
}
_argv = sys.argv[1:]
SYM = 'spx'
for i, a in enumerate(_argv):
    if a == '--symbol' and i + 1 < len(_argv):
        SYM = _argv[i + 1].strip().lower()
    elif a.startswith('--symbol='):
        SYM = a.split('=', 1)[1].strip().lower()
if SYM not in SYMBOLS:
    print('UNKNOWN SYMBOL: %s (expected one of: %s)' % (SYM, ', '.join(sorted(SYMBOLS))))
    sys.exit(2)
CFG = SYMBOLS[SYM]
PFX = CFG['prefix']

# 防重複的判定完全建立在「這份資料檔是本系統的」之上。
# 若資料檔其實屬於另一套，VERDICT 會是假的，且據以寫入的帳本無法回溯修復。
import guard
guard.require_symbol(os.path.join(BASE, CFG['data']), SYM.upper(),
                     'duplicate-check source')
guard.cross_check(BASE)


def load(p):
    try:
        return json.load(io.open(p, encoding='utf-8'))
    except Exception as e:
        return {'__error__': repr(e)}

td = load(os.path.join(BASE, CFG['data']))
la = load(os.path.join(REPO, 'docs', '%slast_analysis.json' % PFX))
tr = load(os.path.join(REPO, 'docs', '%strack_record.json' % PFX))
pl = load(os.path.join(REPO, 'docs', '%spnl_ledger.json' % PFX))

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
    'symbol                     : %s' % SYM.upper(),
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
        'ACTION : STOP. Do NOT analyze. Re-run fetch_today.py%s and read its error.'
        % ('' if SYM == 'spx' else ' --symbol ndx'),
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
io.open(os.path.join(BASE, CFG['out']), 'w', encoding='utf-8', newline='\n').write(out + '\n')
print(out)
sys.exit(0)
