"""影子比對：從 git 取分析 commit 前後的帳本，用固定公式重算，逐欄比對實跑結果。只讀 git，不寫任何帳本。

  python scripts/shadow_check.py --symbol spx --since 2026-11-04 [--report scripts/shadow_check_spx.txt] [--all]
  python scripts/shadow_check.py --symbol ndx <commit> [<commit> …]

輸入：today_data 取 git 裡 data/ 快照（同 trade_date 的最新一份；快照還沒進來時改用本機 scripts/today_data.txt）。實跑帳本有記下的輸入（判定日 OHLC、前收、收盤、VIX／VXN、
amplitude、NDX 的 technicals 與 regime）以帳本為準，和快照不同的欄位列在報告的「輸入修正」。
敘事：直接取實跑寫進帳本的敘事文字，所以剩下的差異只會出在公式與模板字串。有數值差異時結束碼為 1。
"""
import argparse
import copy
import datetime
import json
import os
import subprocess
import sys
import tempfile

import ndx_daily_mech
import ndx_last_mech
import spx_daily_mech
from mech_lib import ld, numeric, sv, walk_diffs

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYM = {'spx': {'files': spx_daily_mech.FILES, 'last': 'last_analysis.json', 'data': 'data/today_data.txt', 'local': 'scripts/today_data.txt', 'vol': 'vix'},
       'ndx': {'files': ndx_daily_mech.FILES + ('ndx_last_analysis.json',), 'last': 'ndx_last_analysis.json', 'data': 'data/ndx_today_data.txt',
               'local': 'scripts/ndx_today_data.txt', 'vol': 'vxn'}}
SPX_NARR = ('rating', 'news_check', 'macro_layer', 'sector_rotation', 'breadth', 'regime_check', 'six_factors', 'catalysts', 'event_week')
SPX_MECH_PRED = ('geometry_A', 'shadow_orders', 'no_trade', 'strategies')
SPX_MECH_RULES = ('as_of', 'basis', 'rule63', 'rule64', 'rule65', 'rule66', 'rule16', 'rule17')
NDX_NARR = ('rating', 'data_quality', 'catalysts', 'news_check_rule49', 'candidate_updates')
NDX_NARR_SUB = {'amplitude': ('note',), 'volatility_scale': ('note',), 'breadth': ('read',), 'sector': ('read',), 'macro': ('read',),
                'regime_check': ('alignment',), 'backtest_prev': ('actual', 'shadow', 'gap_day')}
NDX_MECH_PRED = ('short_bias', 'strategies', 'strategy_status', 'geometry_A', 'shadow_orders')
NDX_MECH_NOTES = 5


def git(*args):
    r = subprocess.run(['git', '-C', REPO, *args], capture_output=True, text=True, encoding='utf-8')
    if r.returncode:
        raise SystemExit(f"git {' '.join(args)} 失敗：{r.stderr.strip()}")
    return r.stdout


def show(rev, path):
    return json.loads(git('show', f'{rev}:{path}'))


def analysis_commits(symbol, since, ref='HEAD'):
    """報告日 ≥ since 的分析 commit（last_analysis 的 trade_date 有變動者），由舊到新。"""
    last = f"docs/{SYM[symbol]['last']}"
    start = (datetime.date.fromisoformat(since) - datetime.timedelta(days=7)).isoformat()
    out = []
    for sha in git('log', '--reverse', '--format=%H', f'--since={start}', ref, '--', last).split():
        a = show(sha, last)
        if a.get('trade_date', '') >= since and a.get('trade_date') != show(f'{sha}^', last).get('trade_date'):
            out.append(sha)
    return out


def snapshots(symbol, dates, ref='HEAD'):
    """{trade_date: today_data}：每個 trade_date 取 git 裡最新一份 data/ 快照。"""
    want, got = set(dates), {}
    for sha in git('log', '--format=%H', ref, '--', SYM[symbol]['data']).split():
        try:
            d = show(sha, SYM[symbol]['data'])
        except ValueError:
            continue
        if d.get('trade_date') in want and d['trade_date'] not in got:
            got[d['trade_date']] = d
        if want <= set(got) or d.get('trade_date', '9') < min(want):
            break
    return got


def fix_inputs(symbol, td, after, t):
    """把實跑帳本記下的輸入寫回 today_data，回傳改了哪些欄位。"""
    la = after[SYM[symbol]['last']]
    am = la['amplitude']
    day = td['trade_date']
    changed = []

    def put(d, k, v, name):
        if d.get(k) != v:
            changed.append(f'{name}: {d.get(k)} → {v}')
            d[k] = v
    for k in ('close', 'change_pct', SYM[symbol]['vol']):
        put(td, k, la[k], k)
    amp = td['amplitude']
    for k in ('stale', 'caveat'):
        if k in amp:
            changed.append(f'amplitude.{k}: 移除')
            del amp[k]
    put(amp, 'as_of', day, 'amplitude.as_of')
    keys = {'amp_forecast_pct': 'A_pct', 'r0_rule27_ref_pct': 'r0_ref_pct', 'c': 'c', 'vol_pct_1y': 'vol_pct_1y', 'realized_vs_implied_63d': 'realized_vs_implied_63d'}
    if symbol == 'ndx':
        keys.update(amp_forecast_pts='A_pts', atr14_pct='atr14_pct')
    for k, v in keys.items():
        put(amp, k, am[v], f'amplitude.{k}')
    put(amp, 'band_50_pct', [am['band_lo'], am['band_hi']], 'amplitude.band_50_pct')
    if symbol == 'spx':
        pe = [x for x in after['pnl_ledger.json']['entries'] if x.get('eval_date') == t][-1]
        o = {'open': pe['ohlc']['o'], 'high': pe['ohlc']['h'], 'low': pe['ohlc']['l'], 'close': pe['ohlc']['c']}
    else:
        pe = [x for x in after['ndx_pnl_ledger.json']['entries'] if x.get('eval_date') == t][-1]
        o = dict(pe['eval_ohlc'])
        for k, v in la['technicals'].items():
            put(td, k, v, k)
        rg, h1 = td['regime'], td['regime']['horizon_1d']
        r1, r5 = la['regime_check']['h1d'], la['regime_check']['h5d']
        for d, k, v, name in ((h1, 'regime_avg_1d', r1['avg'], 'h1d.avg'), (h1, 'base_1d_pullback', r1['base'], 'h1d.base'), (h1, 'regime_avg_vs_base', r1['vs_base'], 'h1d.vs_base'),
                              (rg, 'regime_avg_5d', r5['avg'], 'h5d.avg'), (rg, 'base_5d_pullback', r5['base'], 'h5d.base'), (rg, 'regime_avg_vs_base', r5['vs_base'], 'h5d.vs_base')):
            put(d, k, v, f'regime.{name}')
        for dim, key in (('vxn', 'vxn'), ('trend', 'trend'), ('ma20', 'ma20_ext')):
            put(h1[key], 'pullback_1d', r1[dim], f'regime.h1d.{dim}')
            put(rg[key], 'pullback_5d', r5[dim], f'regime.h5d.{dim}')
    if t == day:
        for k, v in o.items():
            if k != 'close':
                put(td, k, v, k)
        put(td, 'prev_close', pe['basis_close'], 'prev_close')
    else:
        rows = td['recent_5']
        i = [j for j, r in enumerate(rows) if r['date'] == t][0]
        for k, v in o.items():
            put(rows[i], k, v, f'recent_5[{t}].{k}')
        put(rows[i - 1], 'close', pe['basis_close'], f'recent_5[{rows[i - 1]["date"]}].close')
    return changed


def spx_narrative(before, after):
    tr, pl, la = (after[f] for f in spx_daily_mech.FILES)
    trb, plb, lab = (before[f] for f in spx_daily_mech.FILES)
    prev = tr['entries'][-2]
    sh = pl['shadow_ledger']['entries'][len(plb['shadow_ledger']['entries']):]
    track = {'grade_note': prev['grade_note'], 'bias': tr['entries'][-1]['bias'], 'amp_note': tr['amp_track']['entries'][-1]['note']}
    if tr['summary'].get('gap_note') != trb['summary'].get('gap_note'):
        track['gap_note'] = tr['summary']['gap_note'][len(trb['summary'].get('gap_note', '')):]
    rc, rcb = la['rule_candidates'], lab['rule_candidates']
    return {'track': track,
            'pnl': {'day_note': pl['entries'][-2]['day_note'], 'honest_read': pl['summary']['honest_read'],
                    **{f"shadow_note_{x['side']}": x['note'] for x in sh},
                    'shadow_fill_time_et': {x['side']: x['fill_time_et'] for x in sh if x.get('fill_time_et')},
                    'shadow_stop_time_et': {x['side']: x['stop_time_et'] for x in sh if x.get('stop_time_et')}},
            'last_analysis': {**{k: la[k] for k in SPX_NARR if k in la},
                              'amplitude': {'note': la['amplitude']['note']},
                              'predictions': {k: v for k, v in la['predictions'].items() if k not in SPX_MECH_PRED},
                              'backtest_prev': {k: v for k, v in la['backtest_prev'].items() if k in ('summary', 'gap_day')},
                              'rule_status': {k: v for k, v in la['rule_status'].items() if k not in SPX_MECH_RULES}},
            'rule_candidates_append': {k: rc[k][len(rcb.get(k, '')):] for k in rc if rc[k] != rcb.get(k)}}


def ndx_narrative(before, after):
    tr, pl, la = (after[f] for f in SYM['ndx']['files'])
    trb = before['ndx_track_record.json']
    prev = tr['entries'][-2]
    sh = [x for x in pl['shadow_ledger']['entries'] if x['eval_date'] == prev['actual_date']]
    track = {'note': prev['note'], 'sample_caveat': tr['summary']['sample_caveat'], 'brier_honest_read': tr['summary']['brier']['honest_read'],
             'amp_note': tr['amp_track']['entries'][-1]['note']}
    gap = [v for k, v in tr['summary'].items() if k.startswith('gap_note_') and k not in trb['summary']]
    if gap:
        track['gap_note'] = gap[0]
    pnl = {'day_note': pl['entries'][-1]['day_note'], 'honest_read': pl['summary']['honest_read'],
           **{f"fill_type_{x['side']}": x['fill_type'] for x in sh}, **{f"exit_type_{x['side']}": x['exit_type'] for x in sh if x.get('exit_type')}}
    gap = [v for k, v in pl.items() if k.startswith('gap_note_') and k not in before['ndx_pnl_ledger.json']]
    if gap:
        pnl['gap_note'] = gap[0]
    L = {k: la[k] for k in NDX_NARR if k in la}
    L.update({k: {s: la[k][s] for s in subs if s in la[k]} for k, subs in NDX_NARR_SUB.items()})
    cc = la['spx_cross_check']
    L['spx_cross_check'] = {'ndx': {'band': cc['ndx']['band']}, 'spx': {'band': cc['spx']['band']}, 'verdict': cc['verdict']}
    L['predictions'] = {k: v for k, v in la['predictions'].items() if k not in NDX_MECH_PRED}
    return {'track': track, 'pnl': pnl, 'last_analysis': L, 'system_rules_notes_extra': la['system_rules_notes'][NDX_MECH_NOTES:]}


def ndx_aux(after):
    la = after['ndx_last_analysis.json']
    return {'volatility_scale': {k: v for k, v in la['volatility_scale'].items() if k not in ('A_pct', 'A_pts', 'spx_A_pct', 'A_ratio_ndx_spx', 'note')},
            'breadth': {k: v for k, v in la['breadth'].items() if k != 'read'},
            'sector': {k: v for k, v in la['sector'].items() if k != 'read'},
            'macro': {k: v for k, v in la['macro'].items() if k != 'read'}}


def replay(symbol, sha, snaps):
    files, last = SYM[symbol]['files'], SYM[symbol]['last']
    before = {f: show(f'{sha}^', f'docs/{f}') for f in files}
    after = {f: show(sha, f'docs/{f}') for f in files}
    day, rep, t = after[last]['amplitude']['basis_date'], after[last]['trade_date'], before[last]['amplitude']['target_session']
    if day not in snaps:
        raise SystemExit(f'{symbol} {sha[:7]}：git 裡找不到 trade_date {day} 的 {SYM[symbol]["data"]} 快照')
    td = copy.deepcopy(snaps[day])
    fixed = fix_inputs(symbol, td, after, t)
    with tempfile.TemporaryDirectory() as d:
        for f, o in before.items():
            sv(os.path.join(d, f), o)
        if symbol == 'spx':
            nar = spx_narrative(before, after)
            mech, _ = spx_daily_mech.build(d, td, nar, rep)
        else:
            nar = ndx_narrative(before, after)
            mech, _ = ndx_daily_mech.build(d, td, nar, rep)
            out, _ = ndx_last_mech.build(d, mech, td, ndx_aux(after), show(f'{sha}^', 'docs/last_analysis.json'), nar, rep)
            mech.update(out)
    return {'sha': sha, 'report_date': rep, 'trade_date': day, 'eval_date': t, 'inputs_fixed': fixed,
            'diffs': [(f, *x) for f in files for x in walk_diffs(mech[f], after[f])], 'mech': mech, 'after': after, 'today': td, 'narrative': nar}


def replay_all(symbol, shas):
    days = [show(s, f"docs/{SYM[symbol]['last']}")['amplitude']['basis_date'] for s in shas]
    snaps = snapshots(symbol, days)
    local = os.path.join(REPO, SYM[symbol]['local'])
    if os.path.exists(local) and (d := ld(local)).get('trade_date') in set(days) - set(snaps):
        snaps[d['trade_date']] = d
    return [replay(symbol, s, snaps) for s in shas]


def fmt(v):
    return json.dumps(v, ensure_ascii=False)[:160]


def side(kind, a, b):
    if kind == 'length':
        return f'筆數 腳本 {a}｜實跑 {b}'
    return f"腳本 {'（無此欄）' if kind == 'only_actual' else fmt(a)}｜實跑 {'（無此欄）' if kind == 'only_mech' else fmt(b)}"


def report_md(symbol, results, show_all=False, tol=0.0):
    lines, bad = [], 0
    for r in results:
        num = [d for d in r['diffs'] if numeric(d[1:], tol)]
        txt = [d for d in r['diffs'] if not numeric(d[1:], tol) and d[1] == 'value']
        key = [d for d in r['diffs'] if not numeric(d[1:], tol) and d[1] != 'value']
        bad += bool(num)
        lines.append(f"## {symbol} {r['sha'][:7]}（報告日 {r['report_date']}，判定 {r['eval_date']}）：數值差異 {len(num)}、字串差異 {len(txt)}、欄位有無 {len(key)}")
        lines += [f'- 輸入修正 {x}' for x in r['inputs_fixed']]
        lines += [f'- 數值 {f}:{p}：{side(k, a, b)}' for f, k, p, a, b in num]
        if show_all:
            lines += [f"- {'字串' if k == 'value' else '欄位有無'} {f}:{p}：{side(k, a, b)}" for f, k, p, a, b in key + txt]
    return '\n'.join(lines) + '\n', bad


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', choices=('spx', 'ndx'), required=True)
    p.add_argument('commits', nargs='*')
    p.add_argument('--since')
    p.add_argument('--all', action='store_true', help='連字串與欄位有無的差異一起列')
    p.add_argument('--tol', type=float, default=0.0)
    p.add_argument('--report')
    a = p.parse_args(argv)
    if not a.commits and not a.since:
        raise SystemExit('給 commit 或 --since')
    shas = [git('rev-parse', c).strip() for c in a.commits] or analysis_commits(a.symbol, a.since)
    text, bad = report_md(a.symbol, replay_all(a.symbol, shas), a.all, a.tol)
    with open(a.report or os.path.join(REPO, 'scripts', f'shadow_check_{a.symbol}.txt'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
