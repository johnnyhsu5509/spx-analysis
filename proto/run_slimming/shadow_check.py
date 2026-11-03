"""稽核每日實跑的記帳數字：從 git 取某次分析 commit 前後的帳本，用固定公式重算，只回報「數值」不一致（文字格式差異不算）。
不改 spx-gh，只讀 git。

  python3 shadow_check.py --symbol spx f45bb65 436057e ...
  python3 shadow_check.py --symbol ndx 24d3ad9 ...
"""
import argparse, json, os, subprocess, sys

H = os.path.dirname(os.path.abspath(__file__))
REPO = r'D:\LICHUNG_Agent\STOCK\spx-gh'
FILES = {'spx': ['track_record.json', 'pnl_ledger.json', 'last_analysis.json'],
         'ndx': ['ndx_track_record.json', 'ndx_pnl_ledger.json', 'ndx_last_analysis.json']}


def git_show(rev, path, out):
    r = subprocess.run(['git', '-C', REPO, 'show', f'{rev}:{path}'], capture_output=True)
    if r.returncode:
        raise SystemExit(f'git show {rev}:{path} 失敗')
    open(out, 'wb').write(r.stdout)


def numeric_diffs(a, b, path, acc):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in set(a) | set(b):
            if k in a and k in b:
                numeric_diffs(a[k], b[k], f'{path}.{k}', acc)
            elif isinstance(a.get(k, b.get(k)), (int, float, bool)) and a.get(k, b.get(k)) is not None:
                acc.append(f'{path}.{k} 只有一邊有：{a.get(k)} vs {b.get(k)}')
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            acc.append(f'{path} 筆數不同：重算 {len(a)} vs 實跑 {len(b)}')
        for i, (x, y) in enumerate(zip(a, b)):
            numeric_diffs(x, y, f'{path}[{i}]', acc)
    elif isinstance(a, bool) or isinstance(b, bool) or isinstance(a, (int, float)) or isinstance(b, (int, float)):
        if a != b and not (isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) <= 0.0006):
            acc.append(f'{path}：重算 {a} vs 實跑 {b}')


def run(a):
    out = []
    for c in a.commits:
        case = f'{a.symbol}_{c}'
        before, after = os.path.join(H, 'fixtures', case + '_before'), os.path.join(H, 'fixtures', case + '_after')
        os.makedirs(before, exist_ok=True)
        os.makedirs(after, exist_ok=True)
        for f in FILES[a.symbol]:
            git_show(f'{c}~1', f'docs/{f}', os.path.join(before, f))
            git_show(c, f'docs/{f}', os.path.join(after, f))
        synth = 'synth_today.py' if a.symbol == 'spx' else 'synth_today_ndx.py'
        subprocess.run([sys.executable, '-I', os.path.join(H, synth), before, after], check=True)
        val = 'validate_spx.py' if a.symbol == 'spx' else 'validate_ndx.py'
        r = subprocess.run([sys.executable, '-I', os.path.join(H, val), case], capture_output=True, text=True, encoding='utf-8', errors='replace')
        work = os.path.join(H, '_work', case)
        rep = open(os.path.join(work, 'validate_report.txt'), encoding='utf-8').read() if os.path.exists(os.path.join(work, 'validate_report.txt')) else r.stderr
        if not rep.startswith('exit=0'):
            out.append(f'## {a.symbol} {c}：重算失敗\n{rep[:600]}')
            continue
        acc = []
        files = FILES[a.symbol] if a.symbol == 'spx' else FILES[a.symbol][:2]
        for f in files:
            numeric_diffs(json.load(open(os.path.join(work, 'out', f), encoding='utf-8')), json.load(open(os.path.join(after, f), encoding='utf-8')), f, acc)
        day = json.load(open(os.path.join(after, FILES[a.symbol][2]), encoding='utf-8')).get('trade_date')
        out.append(f'## {a.symbol} {c}（報告日 {day}）：數值差異 {len(acc)} 處')
        out += [f'- {x}' for x in sorted(acc)[:40]]
    p = os.path.join(H, '_work', f'shadow_check_{a.symbol}.txt')
    open(p, 'w', encoding='utf-8').write('\n'.join(out))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--symbol', choices=('spx', 'ndx'), required=True)
    ap.add_argument('commits', nargs='+')
    run(ap.parse_args())
