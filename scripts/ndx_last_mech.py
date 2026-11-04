"""NDX ndx_last_analysis.json：在 ndx_daily_mech.py 之後執行，數值欄位由帳本、today_data、aux、SPX last_analysis 產生，敘事由 --narrative 提供。

  python scripts/ndx_last_mech.py --docs docs --ledgers <ndx_daily_mech 的輸出> --today scripts/ndx_today_data.txt \\
      --aux ndx_aux.json --spx-last docs/last_analysis.json --narrative narrative_MMDD.json [--out DIR]

SPX 的 A、VIX、regime 直接讀 SPX 當天的 last_analysis.json；SPX 當天還沒跑完就停下。
--aux 是當天另外量的數據（原樣搬進對應區塊）：{"volatility_scale": {"atr14_pct", "range5_pct", …}, "breadth": {…}, "sector": {…}, "macro": {…}}
部位水位（rule59）切換或處於半倉時停下，要求人工處理。不加 --out 只寫 --report。
"""
import argparse
import os

from mech_lib import amp_hit_rate, ld, md, merge, next_bday, position_level, summary_line, sv

K_SHADOW = 0.2
SHALLOW = ('amplitude', 'volatility_scale', 'breadth', 'sector', 'macro', 'regime_check', 'spx_cross_check', 'predictions', 'backtest_prev', 'position_level')
TECH = ('ma5', 'ma20', 'ma50', 'ma200', 'rsi', 'wilder_rsi', 'macd_hist', 'macd_line', 'signal', 'bb_upper', 'bb_lower', 'bb_pct', 'kd_k', 'kd_d')


def band_pos(x, lo, hi):
    return '區間內' if lo <= x <= hi else '低於區間' if x < lo else '高於區間'


def build(docs, ledgers, td, aux, spx, nar=None, report_date=None):
    """ledgers：ndx_daily_mech.build 產生的 {檔名: 帳本}。"""
    nar = nar or {}
    old = ld(os.path.join(docs, 'ndx_last_analysis.json'))
    tr, pl = ledgers['ndx_track_record.json'], ledgers['ndx_pnl_ledger.json']
    if td.get('symbol') != 'NDX' or old.get('symbol') != 'NDX':
        raise SystemExit('today_data 或 ndx_last_analysis 不是 NDX')
    day = td['trade_date']
    rep = report_date or next_bday(day)
    if not spx.get('data_basis', '').startswith(day):
        raise SystemExit(f"SPX last_analysis 的基準 {spx.get('data_basis')} 不是 {day}：SPX 今天還沒跑完")
    t = old['amplitude']['target_session']
    tre = [x for x in tr['entries'] if x.get('actual_date') == t]
    if not tre or tr['entries'][-1].get('basis_date') != day:
        raise SystemExit('帳本還沒以今天的收盤更新：先跑 ndx_daily_mech.py')
    tre = tre[-1]
    am, rg = td['amplitude'], td['regime']
    h1 = rg['horizon_1d']
    C, A, ma200 = td['close'], am['amp_forecast_pts'], td['ma200']
    lim_l, lim_s = round(C - K_SHADOW * A, 2), round(C + K_SHADOW * A, 2)
    spxA = spx['amplitude']['A_pct']
    ratio = round(am['amp_forecast_pct'] / spxA, 3)
    plv = position_level(old['position_level'], C, ma200, day)
    pos_pct, dist, state = plv['pct'], plv['dist_to_switch_pct'], plv['state']
    gaps =tr['amp_track']['summary'].get('gap_days', []) if day != t else []
    gaps = [x for x in gaps if t < x <= day]

    ae, asum = tr['amp_track']['entries'][-1], tr['amp_track']['summary']
    oam = old['amplitude']
    sh = {x['side']: x for x in pl['shadow_ledger']['entries'] if x['eval_date'] == t}
    pe = [x for x in pl['entries'] if x.get('eval_date') == t][-1]
    drift = round((pe['eval_ohlc']['close'] - pe['basis_close']) / sh['long']['A_pts'], 3)
    brier = [x for x in tr['summary']['brier']['per_entry'] if x['report_date'] == tre['report_date']][-1]['brier']
    pos = band_pos(ae['actual_range_pct'], ae['band_lo'], ae['band_hi'])

    def shadow_txt(x):
        if not x['filled']:
            return f"掛 {x['limit']:,.2f}，全日{'低' if x['side'] == 'long' else '高'} {pe['eval_ohlc']['low' if x['side'] == 'long' else 'high']:,.2f} 未成交"
        return f"成交 {x['fill']:,.2f} → {'停損出場' if x['exit'] == x['stop'] else '收盤平倉'} {x['exit']:,.2f} → {x['pnl_A']:+.3f} A"

    n = {
        'index': '^NDX', 'symbol': 'NDX', 'trade_date': rep, 'data_basis': f'{day} US close',
        'close': C, 'change_pct': td['change_pct'], 'vxn': td['vxn'], 'vxn_as_of': day, 'pullback_prob': 50,
        'headline_status': f"Phase 3 恆 50：方向無 edge（rule55，目前無方向規則達標）。主輸出為隔日振幅預報 A {am['amp_forecast_pct']:.2f}%。",
        'rating': '',
        'amplitude': {'basis_date': day, 'target_session': rep, 'A_pct': am['amp_forecast_pct'], 'A_pts': A, 'band_lo': am['band_50_pct'][0],
                      'band_hi': am['band_50_pct'][1], 'r0_ref_pct': am['r0_rule27_ref_pct'], 'c': am['c'], 'vol_pct_1y': am['vol_pct_1y'],
                      'realized_vs_implied_63d': am['realized_vs_implied_63d'], 'atr14_pct': am['atr14_pct'], 'note': ''},
        'direction': {'prob': 50, 'bias': '中性', 'rule': None, 'note': 'Phase 3 恆 50；目前無方向規則達 rule55 門檻'},
        'volatility_scale': {'A_pct': am['amp_forecast_pct'], 'A_pts': A, **aux['volatility_scale'], 'spx_A_pct': spxA, 'A_ratio_ndx_spx': ratio, 'note': ''},
        'data_quality': {},
        'breadth': {**aux['breadth'], 'read': ''},
        'sector': {**aux['sector'], 'read': ''},
        'macro': {**aux['macro'], 'read': ''},
        'catalysts': [],
        'news_check_rule49': '',
        'regime_check': {'direction': 50,
                         'h1d': {'avg': h1['regime_avg_1d'], 'base': h1['base_1d_pullback'], 'vs_base': h1['regime_avg_vs_base'], 'vxn': h1['vxn']['pullback_1d'],
                                 'trend': h1['trend']['pullback_1d'], 'ma20': h1['ma20_ext']['pullback_1d']},
                         'h5d': {'avg': rg['regime_avg_5d'], 'base': rg['base_5d_pullback'], 'vs_base': rg['regime_avg_vs_base'], 'vxn': rg['vxn']['pullback_5d'],
                                 'trend': rg['trend']['pullback_5d'], 'ma20': rg['ma20_ext']['pullback_5d']}, 'alignment': ''},
        'spx_cross_check': {'ndx': {'A_pct': am['amp_forecast_pct'], 'regime_1d_vs_base': h1['regime_avg_vs_base'], 'vxn': td['vxn'], 'band': ''},
                            'spx': {'A_pct': spxA, 'regime_1d_vs_base': spx['regime_check']['h1d']['vs_base'], 'vix': spx['vix'], 'band': ''},
                            'A_ratio': ratio, 'verdict': ''},
        'technicals': {k: td[k] for k in TECH if k in td},
        'predictions': {'short_bias': '中性', 'strategies': {}, 'strategy_status': 'Phase 3 預設休眠（rule57）：本日無已核准的方向 edge → 不掛實單',
                        'geometry_A': {'A_pts': A, 'rows': [{'k': k, 'long': round(C - k * A, 1), 'short': round(C + k * A, 1)} for k in (0.2, 0.4, 0.6, 0.8)]},
                        'shadow_orders': [{'side': 'long', 'order': 'limit_buy', 'limit': lim_l, 'stop_rule': f'成交價 −0.5A（約 −{round(0.5 * A)} 點）', 'exit': '隔日收盤'},
                                          {'side': 'short', 'order': 'limit_sell', 'limit': lim_s, 'stop_rule': f'成交價 +0.5A（約 +{round(0.5 * A)} 點）', 'exit': '隔日收盤'}]},
        'system_rules': old['system_rules'],
        'system_rules_notes': [
            f"rule55：主輸出 A {am['amp_forecast_pct']:.3f}%（直接讀 ndx_today_data.amplitude，未調整）；方向恆 50、bias 中性",
            f'rule56：掛單幾何以 A 為單位；影子單 k={K_SHADOW}、s=0.5',
            f'rule57：預設不掛實單；影子多 {lim_l:.2f}、影子空 {lim_s:.2f} 寫入 shadow_ledger.pending',
            (f"rule58：振幅帳第 {asum['graded']} 筆（{md(t)}）：實際 {ae['actual_range_pct']:.3f}% vs A {ae['A_pct']}%，log_err {ae['log_err']:.3f}、r0 {ae['r0_log_err']:.3f}，{pos}；"
             f"累計覆蓋 {asum['band_coverage_pct']:.1f}%（n={asum['graded']}），平均 log_err A {asum['mean_log_err']:.3f} vs r0 {asum['mean_r0_log_err']:.3f}"
             + ''.join(f'；{md(x)} gap day' for x in gaps)),
            f"rule59：部位水位 {state}（收盤 > MA200 {pos_pct:+.1f}%），自 {old['position_level']['since']} 起維持，今日未切換"],
        'candidate_updates': {'note': '未新增候補；候補上限 15。'},
        'backtest_prev': {'report_date': tre['report_date'],
                          'predicted': f"中性 50（方向無 edge）；振幅 A {oam['A_pct']:.2f}%（50% 區間 {oam['band_lo']:.3f}–{oam['band_hi']:.3f}%）",
                          'actual': f"{md(t)} 收 {pe['eval_ohlc']['close']:,.2f}，{tre['actual_pct']:+.3f}% → {tre['actual_dir']}；振幅 {ae['actual_range_pct']:.3f}%（{pos}）",
                          'grade': tre['grade'], 'brier': brier,
                          'amp': f"{pos}，log_err {ae['log_err']:.3f} vs r0 {ae['r0_log_err']:.3f}（{'A 優於 r0' if ae['log_err'] < ae['r0_log_err'] else 'r0 優於 A'}）",
                          'shadow': f"影子多：{shadow_txt(sh['long'])}；影子空：{shadow_txt(sh['short'])}。同期漂移 {drift:+.3f} A",
                          'pnl': f"預設休眠 → 0bp，累積 {pl['summary']['cumulative_weighted_bp']}bp"},
        'dashboard_url': 'https://johnnyhsu5509.github.io/spx-analysis/ndx/',
        'dated_report_url': f"https://johnnyhsu5509.github.io/spx-analysis/ndx-analysis-{rep.replace('-', '')}.html",
        'position_level': plv,
        'event_day': {'is_event_day': None, 'note': ''},
        'amp_hit_rate': amp_hit_rate(tr['amp_track']['entries']),
    }
    merge(n, nar.get('last_analysis', {}), SHALLOW, deep=('spx_cross_check',))
    n['summary_line'] = summary_line('NDX', n, n['position_level'])
    n['system_rules_notes'] += nar.get('system_rules_notes_extra', [])
    report = {'trade_date': rep, 'eval_date': t, 'lim_l': lim_l, 'lim_s': lim_s, 'pos_pct': pos_pct, 'dist': dist, 'ratio': ratio, 'spxA': spxA,
              'narrative_keys': sorted(nar.get('last_analysis', {}))}
    return {'ndx_last_analysis.json': n}, report


def main(argv=None):
    p = argparse.ArgumentParser()
    for k in ('--docs', '--ledgers', '--today', '--aux', '--spx-last'):
        p.add_argument(k, required=True)
    p.add_argument('--narrative')
    p.add_argument('--report-date')
    p.add_argument('--out')
    p.add_argument('--report', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ndx_last_mech_report.txt'))
    a = p.parse_args(argv)
    ledgers = {f: ld(os.path.join(a.ledgers, f)) for f in ('ndx_track_record.json', 'ndx_pnl_ledger.json')}
    out, report = build(a.docs, ledgers, ld(a.today), ld(a.aux), ld(a.spx_last), ld(a.narrative) if a.narrative else None, a.report_date)
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        for f, o in out.items():
            sv(os.path.join(a.out, f), o)
    report['wrote'] = a.out
    sv(a.report, report)


if __name__ == '__main__':
    main()
