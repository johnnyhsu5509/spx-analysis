"""驗證 ndx_last_mech.py：先跑 validate_ndx.py 產生更新後的兩本帳，再用實跑寫下的敘事重組 ndx_last_analysis 並逐欄比對。"""
import json, os, subprocess, sys
H = os.path.dirname(os.path.abspath(__file__))
case = sys.argv[1] if len(sys.argv) > 1 else 'ndx1022'
spx_case = sys.argv[2] if len(sys.argv) > 2 else 'spx1022'
FX = os.path.join(H, 'fixtures')
before, after = os.path.join(FX, case + '_before'), os.path.join(FX, case + '_after')
work = os.path.join(H, '_work', case)
ld = lambda p: json.load(open(p, encoding='utf-8'))
subprocess.run([sys.executable, '-I', os.path.join(H, 'validate_ndx.py'), case], check=True)
la = ld(os.path.join(after, 'ndx_last_analysis.json'))
MECH_SUB = {
    'amplitude': ('note',), 'volatility_scale': ('note',), 'breadth': ('read',), 'sector': ('read',), 'regime_check': ('alignment',),
    'spx_cross_check': None, 'backtest_prev': ('actual', 'shadow'),
}
nar_la = {}
for k in ('rating', 'data_quality', 'catalysts', 'news_check_rule49', 'macro', 'candidate_updates'):
    nar_la[k] = la[k]
for k, subs in MECH_SUB.items():
    if subs is None:
        nar_la[k] = {'ndx': {'band': la[k]['ndx']['band']}, 'spx': {'band': la[k]['spx']['band']}, 'verdict': la[k]['verdict']}
    else:
        nar_la[k] = {s: la[k][s] for s in subs}
nar_la['macro'] = {'read': la['macro']['read']}
mech_pred = ('short_bias', 'strategies', 'strategy_status', 'geometry_A', 'shadow_orders')
nar_la['predictions'] = {k: v for k, v in la['predictions'].items() if k not in mech_pred}
nar = {'last_analysis': nar_la, 'system_rules_notes_extra': la['system_rules_notes'][5:]}
np_ = os.path.join(work, 'narrative_last.json')
json.dump(nar, open(np_, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
out = os.path.join(work, 'out_last')
r = subprocess.run([sys.executable, '-I', os.path.join(H, 'ndx_last_mech.py'), '--docs', before, '--ledgers', os.path.join(work, 'out'),
                    '--today', os.path.join(before, 'ndx_today_data.txt'), '--aux', os.path.join(before, 'ndx_aux.txt'),
                    '--spx-last', os.path.join(FX, spx_case + '_after', 'last_analysis.json'), '--narrative', np_, '--out', out,
                    '--report', os.path.join(work, 'last_mech_report.txt')], capture_output=True, text=True, encoding='utf-8', errors='replace')
L = [f'exit={r.returncode}', r.stderr[-2000:]]


def diff(a, b, path, acc):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in list(b) + [k for k in a if k not in b]:
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
        acc.append(f'DIFF {path}: mech={json.dumps(a, ensure_ascii=False)[:220]} | actual={json.dumps(b, ensure_ascii=False)[:220]}')


if r.returncode == 0:
    acc = []
    m = ld(os.path.join(out, 'ndx_last_analysis.json'))
    diff(m, la, 'ndx_last_analysis', acc)
    if list(m) != list(la):
        acc.append(f'KEY_ORDER mech={list(m)} | actual={list(la)}')
    L.append(f'===== ndx_last_analysis.json: {len(acc)} 差異')
    L += acc
    L.append('narrative_last.json bytes=' + str(os.path.getsize(np_)))
open(os.path.join(work, 'validate_last_report.txt'), 'w', encoding='utf-8').write('\n'.join(L))
