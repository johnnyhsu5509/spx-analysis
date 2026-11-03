"""驗證 ndx_daily_mech.py：用某次 NDX 實跑前的帳本＋實跑寫下的敘事重算，與實跑結果逐欄比對（只比兩本帳）。"""
import json, os, subprocess, sys
H = os.path.dirname(os.path.abspath(__file__))


def diff(a, b, path, acc):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a:
                acc.append(f'ONLY_ACTUAL {path}.{k} = {json.dumps(b[k], ensure_ascii=False)[:160]}')
            elif k not in b:
                acc.append(f'ONLY_MECH   {path}.{k} = {json.dumps(a[k], ensure_ascii=False)[:160]}')
            else:
                diff(a[k], b[k], f'{path}.{k}', acc)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f'{path}[{i}]', acc)
    elif a != b:
        acc.append(f'DIFF {path}: mech={json.dumps(a, ensure_ascii=False)[:200]} | actual={json.dumps(b, ensure_ascii=False)[:200]}')

case = sys.argv[1] if len(sys.argv) > 1 else 'ndx1022'
FX = os.path.join(H, 'fixtures')
before, after = os.path.join(FX, case + '_before'), os.path.join(FX, case + '_after')
work = os.path.join(H, '_work', case)
os.makedirs(work, exist_ok=True)
ld = lambda d, f: json.load(open(os.path.join(d, f), encoding='utf-8'))
tr_a, pl_a = ld(after, 'ndx_track_record.json'), ld(after, 'ndx_pnl_ledger.json')
prev = tr_a['entries'][-2]
sh = [x for x in pl_a['shadow_ledger']['entries'] if x['eval_date'] == prev['actual_date']]
nar = {'track': {'note': prev['note'], 'sample_caveat': tr_a['summary']['sample_caveat'],
                 'brier_honest_read': tr_a['summary']['brier']['honest_read'], 'amp_note': tr_a['amp_track']['entries'][-1]['note']},
       'pnl': {'day_note': pl_a['entries'][-1]['day_note'], 'honest_read': pl_a['summary']['honest_read'],
               **{f"fill_type_{x['side']}": x['fill_type'] for x in sh},
               **{f"exit_type_{x['side']}": x['exit_type'] for x in sh if x.get('exit_type')}}}
np_ = os.path.join(work, 'narrative.json')
json.dump(nar, open(np_, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
out = os.path.join(work, 'out')
r = subprocess.run([sys.executable, '-I', os.path.join(H, 'ndx_daily_mech.py'), '--docs', before, '--today', os.path.join(before, 'ndx_today_data.txt'),
                    '--narrative', np_, '--out', out, '--report', os.path.join(work, 'mech_report.txt')],
                   capture_output=True, text=True, encoding='utf-8', errors='replace')
L = [f'exit={r.returncode}', r.stderr[-2000:]]
if r.returncode == 0:
    total = 0
    for f in ('ndx_track_record.json', 'ndx_pnl_ledger.json'):
        acc = []
        diff(ld(out, f), ld(after, f), f, acc)
        total += len(acc)
        L.append(f'===== {f}: {len(acc)} 差異')
        L += acc
    L.append(f'TOTAL_DIFFS={total}')
    L.append('narrative.json bytes=' + str(os.path.getsize(np_)))
open(os.path.join(work, 'validate_report.txt'), 'w', encoding='utf-8').write('\n'.join(L))
