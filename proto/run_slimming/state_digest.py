"""SPX／NDX 帳本狀態摘要：取代每日排程傾印 20～40KB 的帳本結構，只輸出今天判定與記帳需要的欄位，並做跨帳本一致性檢查。

用法：python3 state_digest.py --symbol spx|ndx --docs ../docs --out state_digest_spx.txt
只讀不寫帳本。輸出 UTF-8 JSON（約 2～3KB），用 Read 讀。
"""
import argparse, json, os

FILES = {'spx': ('track_record.json', 'pnl_ledger.json', 'last_analysis.json'),
         'ndx': ('ndx_track_record.json', 'ndx_pnl_ledger.json', 'ndx_last_analysis.json')}


def ld(p):
    return json.load(open(p, encoding='utf-8'))


def pick(d, keys):
    return {k: d.get(k) for k in keys if k in d}


def run(a):
    tr_f, pl_f, la_f = FILES[a.symbol]
    tr, pl, la = (ld(os.path.join(a.docs, f)) for f in (tr_f, pl_f, la_f))
    if a.symbol == 'ndx':
        assert la.get('symbol') == 'NDX', 'ndx_last_analysis 的 symbol 不是 NDX'
    s, b = tr['summary'], tr['summary']['brier']
    pend_tr = tr['entries'][-1]
    pl_pend = pl['trades_pending'] if a.symbol == 'ndx' else pl['entries'][-1]
    sh = pl['shadow_ledger']
    amp = la['amplitude']
    checks = {}
    rd = pend_tr['report_date']
    checks['track_pending'] = pend_tr['grade'] == 'pending'
    checks['pnl_pending_same_date'] = pl_pend['report_date'] == rd
    checks['shadow_pending_same_date'] = all(x['report_date'] == rd for x in sh['pending']) and len(sh['pending']) == 2
    checks['amp_target_is_pending_date'] = amp['target_session'] == rd
    checks['last_trade_date_is_pending_date'] = la['trade_date'] == rd
    checks['no_live_trades'] = not (pl_pend.get('trades') if a.symbol == 'ndx' else pl_pend.get('trades_pending'))
    checks['direction_50'] = pend_tr['pullback_prob'] == 50
    if a.symbol == 'spx':
        checks['daily_baseline_keys'] = sum(k.startswith('always_neutral_baseline_') for k in s)
    out = {
        'symbol': a.symbol.upper(),
        'all_checks_ok': all(v is True for k, v in checks.items() if isinstance(v, bool)),
        'checks': checks,
        'last_analysis': {**pick(la, ('trade_date', 'data_basis', 'close', 'change_pct', 'vix', 'vxn', 'pullback_prob')),
                          'amplitude': pick(amp, ('basis_date', 'target_session', 'A_pct', 'A_pts', 'band_lo', 'band_hi', 'r0_ref_pct', 'c', 'vol_pct_1y')),
                          'position_level': pick(la.get('position_level', {}), ('state', 'since', 'pct', 'dist_to_switch_pct')) or None,
                          'key_support': la.get('predictions', {}).get('key_support'),
                          'key_resistance': la.get('predictions', {}).get('key_resistance'),
                          'watch_points': la.get('predictions', {}).get('watch_points')},
        'track_pending': pick(pend_tr, ('report_date', 'basis_close', 'basis_date', 'pullback_prob', 'grade')),
        'track_summary': {**pick(s, ('graded', 'hits', 'half', 'miss', 'rolling_direction_score_pct', 'always_neutral_baseline_pct', 'as_of')),
                          'brier': pick(b, ('included', 'excluded_flat', 'mean_brier'))},
        'amp_track': {'summary': tr['amp_track']['summary'], 'last': pick(tr['amp_track']['entries'][-1], ('report_date', 'A_pct', 'actual_range_pct', 'log_err', 'r0_log_err', 'in_band'))},
        'pnl': {'pending': pick(pl_pend, ('report_date', 'basis_close', 'signal_A_pct', 'signal_A_pts', 'thresholds')),
                'summary': pick(pl['summary'], ('days_evaluated', 'cumulative_weighted_bp', 'trades_filled', 'open_positions'))},
        'shadow': {'pending': [pick(x, ('side', 'limit', 'k', 's', 'A_pts')) for x in sh['pending']], 'summary': sh['summary']},
        'rules': {'system_rules': len(la.get('system_rules', {})),
                  'rule_candidates': sorted(la.get('rule_candidates', {})) if isinstance(la.get('rule_candidates'), dict) else None},
    }
    txt = json.dumps(out, ensure_ascii=False, indent=1)
    open(a.out, 'w', encoding='utf-8').write(txt)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', choices=('spx', 'ndx'), required=True)
    p.add_argument('--docs', required=True)
    p.add_argument('--out', required=True)
    run(p.parse_args())
