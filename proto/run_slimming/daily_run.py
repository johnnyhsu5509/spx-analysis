"""每日一鍵：讀一份合併敘事 JSON，依序跑記帳腳本與 HTML 渲染器，輸出到 --out（原型階段不寫 spx-gh 的 docs）。

  python3 daily_run.py --symbol spx --docs <docs> --today <today_data.txt> --narrative narrative_MMDD.json --css <head.html> --out <輸出資料夾>
  python3 daily_run.py --symbol ndx --docs <docs> --today <ndx_today_data.txt> --aux <ndx_aux.txt> --spx-last <SPX 今天跑完的 last_analysis.json> \\
                       --narrative ... --css ... --out ...

合併敘事 JSON 的區塊（每支腳本只讀自己需要的）：
  SPX：track、pnl、last_analysis、rule_candidates_append、html
  NDX：track、pnl、last_analysis、system_rules_notes_extra、html
"""
import argparse, json, os, subprocess, sys

H = os.path.dirname(os.path.abspath(__file__))


def call(script, *args):
    r = subprocess.run([sys.executable, '-I', os.path.join(H, script), *args], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode:
        raise SystemExit(f'{script} 失敗：{r.stderr[-1500:]}')


def run(a):
    os.makedirs(a.out, exist_ok=True)
    rep = os.path.join(a.out, 'reports')
    os.makedirs(rep, exist_ok=True)
    if a.symbol == 'spx':
        call('spx_daily_mech.py', '--docs', a.docs, '--today', a.today, '--narrative', a.narrative, '--out', a.out, '--report', os.path.join(rep, 'mech.txt'))
        day = json.load(open(os.path.join(a.out, 'last_analysis.json'), encoding='utf-8'))['trade_date']
        html = os.path.join(a.out, f"spx-analysis-{day.replace('-', '')}.html")
        call('render_spx_html.py', '--docs', a.out, '--today', a.today, '--narrative', a.narrative, '--css', a.css, '--out', html)
    else:
        call('ndx_daily_mech.py', '--docs', a.docs, '--today', a.today, '--narrative', a.narrative, '--out', a.out, '--report', os.path.join(rep, 'mech.txt'))
        call('ndx_last_mech.py', '--docs', a.docs, '--ledgers', a.out, '--today', a.today, '--aux', a.aux, '--spx-last', a.spx_last,
             '--narrative', a.narrative, '--out', a.out, '--report', os.path.join(rep, 'last.txt'))
        day = json.load(open(os.path.join(a.out, 'ndx_last_analysis.json'), encoding='utf-8'))['trade_date']
        html = os.path.join(a.out, f"ndx-analysis-{day.replace('-', '')}.html")
        call('render_ndx_html.py', '--last', os.path.join(a.out, 'ndx_last_analysis.json'), '--track', os.path.join(a.out, 'ndx_track_record.json'),
             '--pnl', os.path.join(a.out, 'ndx_pnl_ledger.json'), '--today', a.today, '--narrative', a.narrative, '--css', a.css, '--out', html)
    open(os.path.join(rep, 'done.txt'), 'w', encoding='utf-8').write(html)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', choices=('spx', 'ndx'), required=True)
    for k in ('--docs', '--today', '--narrative', '--css', '--out'):
        p.add_argument(k, required=True)
    p.add_argument('--aux')
    p.add_argument('--spx-last')
    run(p.parse_args())
