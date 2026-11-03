"""驗證 daily_run.py：把 10/22 的幾份敘事合併成一份，一鍵跑完，再比對帳本（逐欄）與 HTML（可見文字）。"""
import difflib, html, json, os, re, subprocess, sys
H = os.path.dirname(os.path.abspath(__file__))
W, FX = os.path.join(H, '_work'), os.path.join(H, 'fixtures')
ld = lambda p: json.load(open(p, encoding='utf-8'))
L = []


def merged(parts, out):
    m = {}
    for p in parts:
        m.update(ld(p))
    json.dump(m, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return os.path.getsize(out)


def vis(p):
    x = re.sub(r'<[^>]+>', '\n', open(p, encoding='utf-8').read().split('<body>', 1)[1])
    return [ln.strip() for ln in html.unescape(x).split('\n') if ln.strip()]


def same(a, b):
    return ld(a) == ld(b)


cases = {
    'spx': dict(parts=[f'{W}/spx1022/narrative.json', f'{W}/html1022/narrative_html.json'], css=f'{W}/html1022/report_head.html',
                docs=f'{FX}/spx1022_before', today=f'{FX}/spx1022_before/today_data.txt', extra=[],
                ledgers=['track_record.json', 'pnl_ledger.json', 'last_analysis.json'], after=f'{FX}/spx1022_after',
                real=r'D:\LICHUNG_Agent\STOCK\spx-gh\docs\spx-analysis-20261022.html'),
    'ndx': dict(parts=[f'{W}/ndx1022/narrative.json', f'{W}/ndx1022/narrative_last.json', f'{W}/ndxhtml1022/narrative_html.json'], css=f'{W}/ndxhtml1022/ndx_head.html',
                docs=f'{FX}/ndx1022_before', today=f'{FX}/ndx1022_before/ndx_today_data.txt',
                extra=['--aux', f'{FX}/ndx1022_before/ndx_aux.txt', '--spx-last', f'{FX}/spx1022_after/last_analysis.json'],
                ledgers=['ndx_track_record.json', 'ndx_pnl_ledger.json', 'ndx_last_analysis.json'], after=f'{FX}/ndx1022_after',
                real=r'D:\LICHUNG_Agent\STOCK\spx-gh\docs\ndx-analysis-20261022.html'),
}
for sym, c in cases.items():
    nar = os.path.join(W, f'merged_{sym}1022.json')
    size = merged(c['parts'], nar)
    out = os.path.join(W, f'daily_run_{sym}')
    r = subprocess.run([sys.executable, '-I', os.path.join(H, 'daily_run.py'), '--symbol', sym, '--docs', c['docs'], '--today', c['today'], '--narrative', nar,
                        '--css', c['css'], '--out', out, *c['extra']], capture_output=True, text=True, encoding='utf-8', errors='replace')
    L.append(f'== {sym}: exit={r.returncode} merged_narrative={size} bytes {r.stderr[-800:]}')
    if r.returncode:
        continue
    for f in c['ledgers']:
        L.append(f"   {f}: {'一致' if same(os.path.join(out, f), os.path.join(c['after'], f)) else '有差異'}")
    h = open(os.path.join(out, 'reports', 'done.txt'), encoding='utf-8').read()
    ratio = difflib.SequenceMatcher(None, vis(h), vis(c['real']), autojunk=False).ratio()
    L.append(f'   HTML 可見文字相似度 {ratio:.4f}（{os.path.basename(h)}）')
open(os.path.join(W, 'validate_daily_run.txt'), 'w', encoding='utf-8').write('\n'.join(L))
