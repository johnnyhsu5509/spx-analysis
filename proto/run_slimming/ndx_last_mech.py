"""NDX ndx_last_analysis.json 機械部分原型（對應每日手寫的 ndx_last_MMDD.py）。

在 ndx_daily_mech.py 寫完兩本帳之後執行：從更新後的帳本取振幅帳／影子帳結果，從 today_data、aux、SPX last_analysis 取數，
組出整份 ndx_last_analysis；敘事欄位由 --narrative 提供。
跟手寫版的差別：SPX 的 A、regime、VIX 直接讀 SPX 的 last_analysis.json，不手打；部位水位一旦切換就停下要求人工處理。
"""
import argparse, datetime, json, os

K_SHADOW = 0.2
SHALLOW = ('amplitude', 'volatility_scale', 'breadth', 'sector', 'macro', 'regime_check', 'spx_cross_check', 'predictions', 'backtest_prev', 'position_level')


def ld(p):
    return json.load(open(p, encoding='utf-8'))


def md(d):
    t = datetime.date.fromisoformat(d)
    return f'{t.month}/{t.day}'


def next_bday(d):
    t = datetime.date.fromisoformat(d) + datetime.timedelta(days=1)
    while t.weekday() >= 5:
        t += datetime.timedelta(days=1)
    return t.isoformat()


def run(a):
    td, ax, spx = ld(a.today), ld(a.aux), ld(a.spx_last)
    old = ld(os.path.join(a.docs, 'ndx_last_analysis.json'))
    tr = ld(os.path.join(a.ledgers, 'ndx_track_record.json'))
    pl = ld(os.path.join(a.ledgers, 'ndx_pnl_ledger.json'))
    nar = ld(a.narrative) if a.narrative else {}
    assert td['symbol'] == 'NDX' and old['symbol'] == 'NDX'
    day = td['trade_date']
    rep = a.report_date or next_bday(day)
    assert spx['data_basis'].startswith(day), f"SPX last_analysis 的基準 {spx['data_basis']} 不是 {day}：SPX 今天還沒跑完"
    am, rg = td['amplitude'], td['regime']
    h1 = rg['horizon_1d']
    C, A, ma200 = td['close'], am['amp_forecast_pts'], td['ma200']
    lim_l, lim_s = round(C - K_SHADOW * A, 2), round(C + K_SHADOW * A, 2)
    spxA = spx['amplitude']['A_pct']
    ratio = round(am['amp_forecast_pct'] / spxA, 3)
    pos_pct = round((C / ma200 - 1) * 100, 2)
    dist = round((1 - ma200 / C) * 100, 2)
    state = '正常' if C > ma200 else '半倉'
    if state != old['position_level']['state']:
        raise SystemExit(f"部位水位切換 {old['position_level']['state']} → {state}：rule59 事件，請人工處理（含 position_gate.events）")
    if state != '正常':
        raise SystemExit('部位水位為半倉：原型只驗證過正常狀態的文字模板，請人工處理')
    pos = {'state': state, 'close': C, 'ma200': ma200, 'pct': pos_pct, 'since': old['position_level']['since'], 'switched_today': False,
           'data_missing': False, 'basis_date': day, 'dist_to_switch_pct': dist, 'note': '收盤需再跌約 %.1f%% 才轉半倉' % dist}

    ae = tr['amp_track']['entries'][-1]
    asum = tr['amp_track']['summary']
    oam = old['amplitude']
    sh = {x['side']: x for x in pl['shadow_ledger']['entries'] if x['eval_date'] == day}
    tre = [x for x in tr['entries'] if x.get('actual_date') == day][-1]
    pe = [x for x in pl['entries'] if x.get('eval_date') == day][-1]
    drift = round((C - pe['basis_close']) / sh['long']['A_pts'], 3)
    brier = [x for x in tr['summary']['brier']['per_entry'] if x['report_date'] == tre['report_date']][-1]['brier']

    def shadow_txt(x):
        if not x['filled']:
            return f"掛 {x['limit']:,.2f}，全日{'低' if x['side'] == 'long' else '高'} {(td['low'] if x['side'] == 'long' else td['high']):,.2f} 未成交"
        how = '停損出場' if x['exit'] == x['stop'] else '收盤平倉'
        return f"成交 {x['fill']:,.2f} → {how} {x['exit']:,.2f} → {x['pnl_A']:+.3f} A"

    n = {
        'index': '^NDX', 'symbol': 'NDX', 'trade_date': rep, 'data_basis': f'{day} US close',
        'close': C, 'change_pct': td['change_pct'], 'vxn': td['vxn'], 'vxn_as_of': day,
        'pullback_prob': 50,
        'headline_status': 'Phase 3 恆 50：方向無 edge（rule55，目前無方向規則達標）。主輸出為隔日振幅預報 A %.2f%%。' % am['amp_forecast_pct'],
        'rating': '',
        'amplitude': {'basis_date': day, 'target_session': rep, 'A_pct': am['amp_forecast_pct'], 'A_pts': A, 'band_lo': am['band_50_pct'][0], 'band_hi': am['band_50_pct'][1],
                      'r0_ref_pct': am['r0_rule27_ref_pct'], 'c': am['c'], 'vol_pct_1y': am['vol_pct_1y'], 'realized_vs_implied_63d': am['realized_vs_implied_63d'],
                      'atr14_pct': am['atr14_pct'], 'note': ''},
        'direction': {'prob': 50, 'bias': '中性', 'rule': None, 'note': 'Phase 3 恆 50；目前無方向規則達 rule55 門檻'},
        'volatility_scale': {'A_pct': am['amp_forecast_pct'], 'A_pts': A, 'atr14_pct': ax['ndx_atr14_pct'], 'range5_pct': ax['ndx_range5_pct'], 'spx_A_pct': spxA,
                             'A_ratio_ndx_spx': ratio, 'atr_ratio_ndx_spx': ax['atr_ratio'], 'note': ''},
        'data_quality': {},
        'breadth': {'qqqe_qqq_ratio': ax['breadth']['ratio'], 'chg_1d_pct': ax['breadth']['chg_1d_pct'], 'chg_5d_pct': ax['breadth']['chg_5d_pct'],
                    'vs_ma20_pct': ax['breadth']['vs_ma20_pct'], 'read': ''},
        'sector': {'soxx_close': ax['sector']['soxx_close'], 'soxx_chg_pct': ax['sector']['soxx_chg_pct'], 'soxx_chg5_pct': ax['sector']['soxx_chg5_pct'],
                   'soxx_chg10_pct': ax['sector']['soxx_chg10_pct'], 'read': ''},
        'macro': {k: ax[k] for k in ('tnx', 'vix', 'vxn', 'dxy', 'brent', 'wti')},
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
        'technicals': {k: td[k] for k in ['ma5', 'ma20', 'ma50', 'ma200', 'rsi', 'macd_hist', 'macd_line', 'signal', 'bb_upper', 'bb_lower', 'bb_pct', 'kd_k', 'kd_d']},
        'predictions': {'short_bias': '中性', 'strategies': {}, 'strategy_status': 'Phase 3 預設休眠（rule57）：本日無已核准的方向 edge → 不掛實單',
                        'geometry_A': {'A_pts': A, 'rows': [{'k': k, 'long': round(C - k * A, 1), 'short': round(C + k * A, 1)} for k in (0.2, 0.4, 0.6, 0.8)]},
                        'shadow_orders': [{'side': 'long', 'order': 'limit_buy', 'limit': lim_l, 'stop_rule': '成交價 −0.5A（約 −%d 點）' % round(0.5 * A), 'exit': '隔日收盤'},
                                          {'side': 'short', 'order': 'limit_sell', 'limit': lim_s, 'stop_rule': '成交價 +0.5A（約 +%d 點）' % round(0.5 * A), 'exit': '隔日收盤'}]},
        'system_rules': old['system_rules'],
        'system_rules_notes': [
            'rule55：主輸出 A %.3f%%（直接讀 ndx_today_data.amplitude，未調整）；方向恆 50、bias 中性' % am['amp_forecast_pct'],
            'rule56：掛單幾何以 A 為單位；影子單 k=0.2、s=0.5',
            'rule57：預設不掛實單；影子多 %.2f、影子空 %.2f 寫入 shadow_ledger.pending' % (lim_l, lim_s),
            'rule58：振幅帳第 %d 筆（%s）：實際 %.3f%% vs A %s%%，log_err %.3f、r0 %.3f，%s；累計覆蓋 %.1f%%（n=%d）' % (
                asum['graded'], md(day), ae['actual_range_pct'], ae['A_pct'], ae['log_err'], ae['r0_log_err'], '區間內' if ae['in_band'] else '區間外', asum['band_coverage_pct'], asum['graded']),
            'rule59：部位水位 %s（收盤 > MA200 %+.1f%%），自 %s 起維持，今日未切換' % (state, pos_pct, pos['since'])],
        'candidate_updates': {'note': '未新增候補；候補上限 15。'},
        'backtest_prev': {'report_date': tre['report_date'],
                          'predicted': '中性 50（方向無 edge）；振幅 A %s%%（50%% 區間 %s–%s%%）' % (oam['A_pct'], oam['band_lo'], oam['band_hi']),
                          'actual': f"{md(day)} 收 {C:,.2f}，{tre['actual_pct']:+.2f}% → {tre['actual_dir']}；振幅 {ae['actual_range_pct']:.3f}%",
                          'grade': tre['grade'], 'brier': brier,
                          'amp': '%s，log_err %.3f vs r0 %.3f（%s）' % ('區間內' if ae['in_band'] else '區間外', ae['log_err'], ae['r0_log_err'], 'A 優於 r0' if ae['log_err'] < ae['r0_log_err'] else 'r0 優於 A'),
                          'shadow': f"影子多：{shadow_txt(sh['long'])}；影子空：{shadow_txt(sh['short'])}。同期漂移 {drift:+.3f} A",
                          'pnl': f"預設休眠 → 0bp，累積 {pl['summary']['cumulative_weighted_bp']}bp"},
        'dashboard_url': 'https://johnnyhsu5509.github.io/spx-analysis/ndx/',
        'dated_report_url': f"https://johnnyhsu5509.github.io/spx-analysis/ndx-analysis-{rep.replace('-', '')}.html",
        'position_level': pos,
    }
    L = nar.get('last_analysis', {})
    for k, v in L.items():
        if k in SHALLOW and isinstance(v, dict) and isinstance(n.get(k), dict):
            for kk, vv in v.items():
                if isinstance(vv, dict) and isinstance(n[k].get(kk), dict):
                    n[k][kk].update(vv)
                else:
                    n[k][kk] = vv
        else:
            n[k] = v
    n['system_rules_notes'] += nar.get('system_rules_notes_extra', [])
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        open(os.path.join(a.out, 'ndx_last_analysis.json'), 'w', encoding='utf-8', newline='\n').write(json.dumps(n, ensure_ascii=False, indent=1) + '\n')
    open(a.report, 'w', encoding='utf-8').write(json.dumps({'trade_date': rep, 'lim_l': lim_l, 'lim_s': lim_s, 'pos_pct': pos_pct, 'dist': dist, 'ratio': ratio,
                                                         'spxA': spxA, 'narrative_keys': sorted(L)}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for k in ('--docs', '--ledgers', '--today', '--aux', '--spx-last'):
        p.add_argument(k, required=True)
    p.add_argument('--narrative')
    p.add_argument('--report-date')
    p.add_argument('--out')
    p.add_argument('--report', default='ndx_last_mech_report.txt')
    run(p.parse_args())
