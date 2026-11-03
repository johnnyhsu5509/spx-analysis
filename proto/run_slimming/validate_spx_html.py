"""驗證 render_spx_html.py：從實跑 HTML 抽出敘事片段 → 用實跑後的帳本重新渲染 → 比對兩份 HTML 的可見文字。

python validate_spx_html.py <實跑 HTML> <實跑後帳本資料夾> <today_data> <輸出資料夾>
"""
import difflib, html, json, os, re, subprocess, sys
H_ = os.path.dirname(os.path.abspath(__file__))
src, docs, today, work = sys.argv[1:5]
os.makedirs(work, exist_ok=True)
t = open(src, encoding='utf-8').read()
head, body = t.split('<body>', 1)
head = re.sub(r'<title>[^<]*</title>', '<title>SPX 日線分析 __DATE__</title>', head)
css = os.path.join(work, 'report_head.html')
open(css, 'w', encoding='utf-8', newline='\n').write(head)


def sect(start, end):
    i = body.index(start)
    j = body.index(end, i + len(start)) if end else len(body)
    return body[i:j]


def notes(s, cls='note'):
    return [m.strip() for m in re.findall(r'<div class="%s"[^>]*>(.*?)</div>' % cls, s, re.S)]


def rows(s):
    out = []
    for tr in re.findall(r'<tr>(.*?)</tr>', s, re.S):
        tds = re.findall(r'<td([^>]*)>(.*?)</td>', tr, re.S)
        if tds:
            out.append(tds)
    return out


s1 = sect('第一區', 'Phase 3 帳本')
s1b = sect('Phase 3 帳本', '第二區')
s2a = sect('第二區', '盤前宏觀層')
s2m = sect('盤前宏觀層', '環境水位（regime）</h3>')
s2r = sect('環境水位（regime）</h3>', '0. 廣度')
s2b = sect('0. 廣度', '1–3.')
s2p = sect('1–3.', '4. 葛蘭威爾')
s2g = sect('4. 葛蘭威爾', '5–6.')
s2c = sect('5–6.', '關鍵位')
s2l = sect('關鍵位', '第三區')
s3f = sect('若要掛單', '影子單（')
s3n = sect('市場筆記速記', None)
kn = re.findall(r'<div class="lb">([^<]*)</div><div class="vl[^"]*">[^<]*</div><div class="nt">(.*?)</div>', s1b)
mk = re.findall(r'<div class="lb">([^<]*)</div><div class="vl[^"]*">[^<]*</div><div class="nt">(.*?)</div>', s2m)
cls_of = lambda attr: (re.search(r'class="([^"]*)"', attr).group(1) if 'class' in attr else '')
pre = re.search(r'<pre>(.*?)</pre>', s3n, re.S).group(1)
regime_pre = re.search(r'<pre>(.*?)</pre>', s2r, re.S).group(1)
nar = {'html': {
    'backtest_notes': notes(s1),
    'ledger_kpi_notes': {'amp': kn[0][1], 'logerr': kn[1][1], 'long': kn[2][1], 'short': kn[3][1]},
    'deviation': notes(s1b, 'warn')[0],
    'rule17_note': notes(s1b)[-1],
    'amp_note': re.search(r'c = [^）]*）。(.*)舊算法 r0', notes(s2a)[0], re.S).group(1),
    'macro_title': re.search(r'盤前宏觀層（(.*?)）</h3>', body).group(1),
    'nq_note': mk[2][1], 'rates_note': mk[3][1],
    'macro_note': notes(s2m)[0],
    'regime_labels': [re.search(r'%s：(.*?) +→' % k, regime_pre).group(1) for k in ('VIX', '趨勢', 'MA20')],
    'regime_warn': notes(s2r, 'warn')[0],
    'breadth_note': notes(s2b)[0],
    'price_rows': [[r[0][1], r[1][1], cls_of(r[2][0]), r[2][1]] for r in rows(s2p)],
    'granville': [list(x) for x in re.findall(r'<div class="gc"><div class="h">(.*?)</div>(.*?)</div>\n', s2g)],
    'chan_note': notes(s2c)[0],
    'elliott_rows': [[r[0][1], r[1][1], cls_of(r[2][0]), r[2][1]] for r in rows(s2c)],
    'bias_note': notes(s2c)[1],
    'levels': [[r[0][1], r[1][1], r[2][1], r[3][1]] for r in rows(s2l)],
    'fill_note': (notes(s3f) or [''])[0],
    'notes_catalyst': html.unescape(re.search(r'今日催化劑：(.*)', pre).group(1)),
    'notes_watch': re.search(r'明日觀察：(.*)', pre).group(1),
    'notes_support': re.search(r'關鍵支撐：(.*)', pre).group(1),
    'notes_resistance': re.search(r'關鍵阻力：(.*)', pre).group(1),
    'footer_note': notes(s3n)[-1],
}}
np_ = os.path.join(work, 'narrative_html.json')
json.dump(nar, open(np_, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
out = os.path.join(work, 'rendered.html')
r = subprocess.run([sys.executable, '-I', os.path.join(H_, 'render_spx_html.py'), '--docs', docs, '--today', today, '--narrative', np_, '--css', css, '--out', out],
                   capture_output=True, text=True, encoding='utf-8', errors='replace')
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
