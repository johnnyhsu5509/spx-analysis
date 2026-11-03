import json, sys, os
d = sys.argv[1]
out = []
def short(v):
    if isinstance(v, str):
        return v[:60] + ('…' if len(v) > 60 else '')
    if isinstance(v, list):
        return f'<list {len(v)}>' if len(v) > 4 or any(isinstance(x, (dict, list)) for x in v) else v
    if isinstance(v, dict):
        return {k: short(x) for k, x in v.items()}
    return v
for name in sys.argv[2:]:
    j = json.load(open(os.path.join(d, name), encoding='utf-8'))
    out.append(f'##### {name} top keys: {list(j.keys())}')
    for k, v in j.items():
        if isinstance(v, dict):
            out.append(f'--- {k}: ' + json.dumps(short(v), ensure_ascii=False))
            for kk, vv in v.items():
                if isinstance(vv, list) and vv and isinstance(vv[0], dict):
                    out.append(f'    {k}.{kk}[-1]: ' + json.dumps(short(vv[-1]), ensure_ascii=False))
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            out.append(f'--- {k} n={len(v)} [-2]: ' + json.dumps(short(v[-2]), ensure_ascii=False))
            out.append(f'--- {k} [-1]: ' + json.dumps(short(v[-1]), ensure_ascii=False))
        else:
            out.append(f'--- {k}: ' + json.dumps(short(v), ensure_ascii=False))
open(os.path.join(d, '_peek.txt'), 'w', encoding='utf-8').write('\n'.join(out))
