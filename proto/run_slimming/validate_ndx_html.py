"""驗證 render_ndx_html.py：從實跑 NDX HTML 抽出敘事 → 用實跑後帳本重新渲染 → 比對可見文字。
python validate_ndx_html.py <實跑 HTML> <實跑後帳本資料夾> <ndx_today_data> <輸出資料夾>
"""
import difflib, html, json, os, re, subprocess, sys
H_ = os.path.dirname(os.path.abspath(__file__))
src, docs, today, work = sys.argv[1:5]
os.makedirs(work, exist_ok=True)
t = open(src, encoding='utf-8').read()
head, body = t.split('<body>', 1)
css = os.path.join(work, 'ndx_head.html')
open(css, 'w', encoding='utf-8', newline='\n').write(re.sub(r'<title>[^<]*</title>', lambda m: m.group(0).replace(re.search(r'\d{4}-\d{2}-\d{2}', m.group(0)).group(0), '__DATE__') if re.search(r'\d{4}-\d{2}-\d{2}', m.group(0)) else m.group(0), head))


def between(a, b):
    i = body.index(a)
    return body[i:body.index(b, i + len(a))]


def box(s, cls):
    return re.search(r'<div class="box %s">\s*(.*?)\s*</div>' % cls, s, re.S).group(1)


def cells(row):
    return [(re.search(r'class="([^"]*)"', c[0]).group(1) if 'class' in c[0] else '', c[1]) for c in re.findall(r'<td([^>]*)>(.*?)</td>', row, re.S)]


s_kpi = between('<div class="kpi">', '<h2>一、')
kn = dict(re.findall(r'<div class="l">([^<]*)</div><div class="v[^"]*">[^<]*</div><div class="n[^"]*">(.*?)</div>', s_kpi))
s1 = between('<h2>一、', '<h2>二、')
trs = re.findall(r'<tr>(.*?)</tr>', s1, re.S)
bt = [cells(r) for r in trs if '<td' in r]
first_tbl = bt[:[i for i, r in enumerate(bt) if r[0][1] == '策略（主帳）'][0]]
shadow = {('long' if '影子多' in r[0][1] else 'short'): r[2][1] for r in first_tbl if '影子' in r[0][1]}
checks = [[r[0][1], r[1][1], r[2][1], r[3][1], r[3][0]] for r in first_tbl[4:]]
s2 = between('<h2>二、', '<h2>三、')
dims = [[c[1] for c in cells(r)] for r in re.findall(r'<tr>(.*?)</tr>', s2, re.S) if '<td' in r]
s3 = between('<h2>三、', '<h2>四、')
s4 = between('<h2>四、', '<h2>五、')
mono4 = re.search(r'<div class="mono">(.*?)</div>', s4, re.S).group(1)
s5 = between('<h2>五、', '<h2>六、')
ft = re.search(r'新聞：(.*?)<br>', body).group(1)
nar = {'html': {
    'title': re.search(r'<h1>(.*?)</h1>', body).group(1),
    'breadth_kpi': kn['QQQE / QQQ'], 'vxn_kpi': kn['VXN'],
    'data_note': re.search(r'<h4>資料註記</h4>\s*(.*?)\s*</div>', body, re.S).group(1),
    'shadow_actual_long': shadow['long'], 'shadow_actual_short': shadow['short'],
    'check_rows': checks,
    'deviation': box(s1, 'warn'),
    'dims': dims,
    'amp_warn': box(s3, 'warn'),
    'regime_labels': [re.search(r'%s：(.*?)→' % x, mono4).group(1) for x in ('VXN', '趨勢', 'MA20')],
    'ndx_band': re.search(r'VXN [\d.]+（(.*?)）', mono4).group(1),
    'spx_band': re.search(r'VIX [\d.]+（(.*?)）', mono4).group(1),
    'cross_label': re.search(r'環境：(.*)', mono4).group(1),
    'cross_note': box(s4, 'warn'),
    'news': box(s5, 'info'),
    'news_sources': ft,
}}
np_ = os.path.join(work, 'narrative_html.json')
json.dump(nar, open(np_, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
out = os.path.join(work, 'rendered.html')
r = subprocess.run([sys.executable, '-I', os.path.join(H_, 'render_ndx_html.py'), '--last', os.path.join(docs, 'ndx_last_analysis.json'),
                    '--track', os.path.join(docs, 'ndx_track_record.json'), '--pnl', os.path.join(docs, 'ndx_pnl_ledger.json'),
                    '--today', today, '--narrative', np_, '--css', css, '--out', out], capture_output=True, text=True, encoding='utf-8', errors='replace')
L = [f'exit={r.returncode}', r.stderr[-3000:]]


def vis(p):
    x = open(p, encoding='utf-8').read().split('<body>', 1)[1]
    x = re.sub(r'<[^>]+>', '\n', x)
    return [ln.strip() for ln in html.unescape(x).split('\n') if ln.strip()]


if r.returncode == 0:
    a, b = vis(out), vis(src)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    L.append(f'visible_lines rendered={len(a)} actual={len(b)} ratio={sm.ratio():.4f}')
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != 'equal':
            L.append(f'--- {tag}\n  MECH: {a[i1:i2]}\n  REAL: {b[j1:j2]}')
    L.append(f'sizes: actual_html={os.path.getsize(src)} narrative_json={os.path.getsize(np_)}')
open(os.path.join(work, 'validate_html_report.txt'), 'w', encoding='utf-8').write('\n'.join(L))
