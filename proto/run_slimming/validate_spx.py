"""驗證 spx_daily_mech.py：用 10/22 實跑前的帳本＋實跑寫下的敘事，重算後與實跑結果逐欄比對。"""
import json, os, subprocess, sys
H = os.path.dirname(os.path.abspath(__file__))
FX = os.path.join(H, 'fixtures')
case = sys.argv[1] if len(sys.argv) > 1 else 'spx1022'
before, after = os.path.join(FX, case + '_before'), os.path.join(FX, case + '_after')
work = os.path.join(H, '_work', case)
os.makedirs(work, exist_ok=True)
ld = lambda d, f: json.load(open(os.path.join(d, f), encoding='utf-8'))
tr_a, pnl_a, la_a, la_b = ld(after, 'track_record.json'), ld(after, 'pnl_ledger.json'), ld(after, 'last_analysis.json'), ld(before, 'last_analysis.json')

prev = tr_a['entries'][-2]
sh_new = [x for x in pnl_a['shadow_ledger']['entries'] if x['eval_date'] == prev['actual_date']]
NARR_LA = ['rating', 'news_check', 'macro_layer', 'sector_rotation', 'breadth', 'regime_check', 'six_factors', 'catalysts', 'event_week']
nar = {
    'track': {'grade_note': prev['grade_note'], 'bias': tr_a['entries'][-1]['bias'], 'amp_note': tr_a['amp_track']['entries'][-1]['note']},
    'pnl': {'day_note': pnl_a['entries'][-2]['day_note'], 'honest_read': pnl_a['summary']['honest_read'],
            **{f"shadow_note_{x['side']}": x['note'] for x in sh_new},
            'shadow_fill_time_et': {x['side']: x['fill_time_et'] for x in sh_new if x.get('fill_time_et')}},
    'last_analysis': {**{k: la_a[k] for k in NARR_LA if k in la_a},
                      'amplitude': {'note': la_a['amplitude']['note']},
                      'predictions': {k: v for k, v in la_a['predictions'].items() if k not in ('geometry_A', 'shadow_orders', 'no_trade', 'strategies')},
                      'backtest_prev': {'summary': la_a['backtest_prev']['summary']},
                      'rule_status': {k: v for k, v in la_a['rule_status'].items() if k not in ('as_of', 'basis', 'rule63', 'rule64', 'rule65', 'rule66', 'rule16', 'rule17')}},
    'rule_candidates_append': {k: la_a['rule_candidates'][k][len(la_b['rule_candidates'][k]):] for k in la_a['rule_candidates']
                               if k in la_b['rule_candidates'] and la_a['rule_candidates'][k] != la_b['rule_candidates'][k]},
}
np_ = os.path.join(work, 'narrative.json')
json.dump(nar, open(np_, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
out = os.path.join(work, 'out')
rp = os.path.join(work, 'mech_report.txt')
r = subprocess.run([sys.executable, '-I', os.path.join(H, 'spx_daily_mech.py'), '--docs', before, '--today', os.path.join(before, 'today_data.txt'),
                    '--narrative', np_, '--out', out, '--report', rp], capture_output=True, text=True, encoding='utf-8', errors='replace')
L = [f'exit={r.returncode}', r.stderr[-2000:]]


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


if r.returncode == 0:
    total = 0
    for f in ('track_record.json', 'pnl_ledger.json', 'last_analysis.json'):
        acc = []
        diff(ld(out, f), ld(after, f), f, acc)
        total += len(acc)
        L.append(f'===== {f}: {len(acc)} 差異')
        L += acc
    L.append(f'TOTAL_DIFFS={total}')
    L.append('narrative.json bytes=' + str(os.path.getsize(np_)))
open(os.path.join(work, 'validate_report.txt'), 'w', encoding='utf-8').write('\n'.join(L))
