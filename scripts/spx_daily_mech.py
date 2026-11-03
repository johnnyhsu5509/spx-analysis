"""SPX 每日記帳（Phase 3 休眠期）：track_record／pnl_ledger／last_analysis 的數值欄位由固定公式產生，敘事由 --narrative 提供。

  python scripts/spx_daily_mech.py --docs docs --today scripts/today_data.txt --narrative narrative_MMDD.json [--out docs] [--report scripts/mech_report.txt]

不加 --out 只寫 --report，不寫任何帳本。會擋下：同一收盤已分析過、amplitude 缺或過期、有實單、方向偏離 50。
敘事欄位見 docs/run_slimming.md。
"""
import argparse
import os

from mech_lib import eval_session, ld, log_err, md, merge, next_bday, shadow_fill, sv

K_ENTRY, S_STOP, DIR_TH = 0.4, 0.5, 0.3
FILES = ('track_record.json', 'pnl_ledger.json', 'last_analysis.json')
SHALLOW = ('amplitude', 'predictions', 'backtest_prev', 'rule_status')
DIR_ZH = {'up': '漲', 'down': '跌', 'flat': '平'}


def direction(chg):
    return 'up' if chg >= DIR_TH else 'down' if chg <= -DIR_TH else 'flat'


def build(docs, td, nar=None, report_date=None):
    nar = nar or {}
    T, P = nar.get('track', {}), nar.get('pnl', {})
    tr, pnl, la = (ld(os.path.join(docs, f)) for f in FILES)
    day = td['trade_date']
    if la.get('data_basis', '').startswith(day):
        raise SystemExit(f'DUPLICATE：last_analysis 已以 {day} 收盤分析過')
    amp = td.get('amplitude')
    if not amp or amp.get('stale') or amp.get('as_of') != day:
        raise SystemExit('amplitude 缺或過期：照 SKILL 寫「振幅資料缺」，本腳本不處理')
    C, chg = td['close'], td['change_pct']
    A_pct, (BLO, BHI) = amp['amp_forecast_pct'], amp['band_50_pct']
    A_pts = round(A_pct * C / 100, 2)
    rep = report_date or next_bday(day)
    LL, SL = round(C - K_ENTRY * A_pts, 2), round(C + K_ENTRY * A_pts, 2)

    e = tr['entries'][-1]
    if e['grade'] != 'pending':
        raise SystemExit(f"track_record 最後一筆不是 pending：{e['report_date']}")
    if e['pullback_prob'] != 50:
        raise SystemExit(f"pullback_prob={e['pullback_prob']}：只支援 Phase 3 方向 50，偏離 50 需要人工記帳")
    pa = la['amplitude']
    t = pa['target_session']
    if t != e['report_date']:
        raise SystemExit(f"振幅預報目標日 {t} 與待判定預測 {e['report_date']} 對不上")
    pe = pnl['entries'][-1]
    if pe['report_date'] != e['report_date']:
        raise SystemExit(f"pnl_ledger 待判定日 {pe['report_date']} 與 track_record {e['report_date']} 對不上")
    if pe['trades_pending']:
        raise SystemExit('有實單 trades_pending：本腳本不處理實單判定，請人工記帳')
    if len(pnl['shadow_ledger']['pending']) != 2 or any(x['report_date'] != e['report_date'] for x in pnl['shadow_ledger']['pending']):
        raise SystemExit('影子單 pending 不是兩張、或 report_date 對不上')
    E, gaps = eval_session(td, t)
    eO, eH, eL, eC, ePC = E['o'], E['h'], E['l'], E['c'], E['pc']
    echg = E['chg'] if E['chg'] is not None else round((eC / ePC - 1) * 100, 2)

    # 方向帳＋Brier
    act_dir = direction(echg)
    g = 'hit' if act_dir == 'flat' else 'half'
    e.update(actual_date=t, actual_pct=echg, actual_dir=act_dir, grade=g,
             grade_note=T.get('grade_note', f'實際 {echg:+.2f}%（收 {eC:,.2f}）＝{act_dir}；方向 50「中性」→ {g}'))
    tr['entries'].append({'report_date': rep, 'basis_close': C, 'pullback_prob': 50,
                          'bias': T.get('bias', f'中性 50（方向無 edge，rule63／rule16）。基準 {md(day)} 收 {C:,.2f}（{chg:+.2f}%）'),
                          'actual_date': f'{rep}(pending)', 'actual_pct': None, 'actual_dir': None, 'grade': 'pending'})
    graded = [x for x in tr['entries'] if x['grade'] in ('hit', 'half', 'miss')]
    s = tr['summary']
    n = len(graded)
    s.update(graded=n, **{k: sum(x['grade'] == v for x in graded) for k, v in (('hits', 'hit'), ('half', 'half'), ('miss', 'miss'))})
    s['rolling_direction_score_pct'] = round((s['hits'] + 0.5 * s['half']) / n * 100, 1)
    if gaps:
        s['gap_days'] = s.get('gap_days', []) + [x for x in gaps if x not in s.get('gap_days', [])]
        s['gap_note'] = s.get('gap_note', '') + T.get('gap_note', '；' + '、'.join(gaps) + ' 為 gap day，未執行分析，無預測留存，不回補不灌水')
    s['as_of'] = rep
    b = s['brier']
    p = e['pullback_prob'] / 100
    brier = None if act_dir == 'flat' else round((p - (1 if act_dir == 'down' else 0)) ** 2, 4)
    if brier is not None:
        b['per_entry'].append({'report_date': e['report_date'], 'p': p, 'outcome': 1 if act_dir == 'down' else 0, 'brier': brier})
    flat = sum(x.get('actual_dir') == 'flat' for x in graded)
    b.update(as_of=rep, included=len(b['per_entry']), excluded_flat=flat,
             mean_brier=round(sum(x['brier'] for x in b['per_entry']) / len(b['per_entry']), 4))
    b['note_latest'] = (f"{e['report_date']}：方向 50 中性遇 {echg:+}%＝{act_dir}（{g}），{'Brier 排除不計' if brier is None else f'Brier {brier}'}。"
                        f"mean_brier {b['mean_brier']}（{b['included']} 筆）")
    base = round((flat + (n - flat) * 0.5) / n * 100, 1)
    s[f"always_neutral_baseline_{rep.replace('-', '')}"] = (f"依 rule17 並列：每天報中性基準 {base}%（{n} 筆，flat {flat}）vs 系統 {s['rolling_direction_score_pct']}%；"
                                                            f"Brier {b['mean_brier']} vs 0.25")

    # 振幅帳
    raw = (eH - eL) / ePC * 100
    act = round(raw, 4)
    le, r0e = log_err(raw, pa['A_pct']), log_err(raw, pa['r0_ref_pct'])
    inb = pa['band_lo'] <= act <= pa['band_hi']
    pos = '區間內' if inb else '低於區間' if act < pa['band_lo'] else '高於區間'
    at = tr['amp_track']
    at['entries'].append({'report_date': e['report_date'], 'basis_date': pa['basis_date'], 'eval_date': t,
                          'A_pct': pa['A_pct'], 'band_lo': pa['band_lo'], 'band_hi': pa['band_hi'], 'r0_ref_pct': pa['r0_ref_pct'],
                          'actual_range_pct': act, 'log_err': le, 'r0_log_err': r0e, 'in_band': inb,
                          'note': T.get('amp_note', f"實際 {act:.2f}% 為 A 的 {act / pa['A_pct']:.2f} 倍、{'落在 50% 區間內' if inb else pos}")})
    es = at['entries']
    asum = at['summary']
    asum.update(graded=len(es), mean_log_err=round(sum(x['log_err'] for x in es) / len(es), 4),
                mean_r0_log_err=round(sum(x['r0_log_err'] for x in es) / len(es), 4),
                band_coverage_pct=round(sum(x['in_band'] for x in es) / len(es) * 100, 1), as_of=rep,
                note=f'樣本 {len(es)} 筆，無統計意義；60 筆後依 rule66 判定')
    if gaps:
        asum['gap_days'] = asum.get('gap_days', []) + gaps

    # P&L 主帳（無實單日）
    ps = pnl['summary']
    pe.update(eval_date=t, ohlc={'o': eO, 'h': eH, 'l': eL, 'c': eC}, results=[], day_weighted_bp=0.0,
              day_note=P.get('day_note', f"**0bp（rule65 預設不掛），累積維持 {ps['cumulative_weighted_bp']}bp。**discretionary_log 不新增"))
    pnl['entries'].append({'report_date': rep, 'eval_date': f'pending({rep} US close)', 'basis_close': C,
                           'thresholds': {'A_pct': A_pct, 'A_pts': A_pts, 'band_50_pct': [BLO, BHI], 'note': 'Phase 3：掛單幾何以 A 為單位（rule64）'},
                           'trades_pending': [],
                           'structure_note': '**Phase 3 預設休眠（rule65）：本日無已核准的方向 edge → 不掛實單。**影子單兩張另記 shadow_ledger'})
    ps['as_of'] = rep
    ps['days_evaluated'] += 1
    if gaps:
        ps['gap_days'] = ps.get('gap_days', []) + [x for x in gaps if x not in ps.get('gap_days', [])]
    gtxt = '、'.join(md(x) for x in gaps) + ' 為 gap day（無預測留存）。' if gaps else ''
    ps['honest_read'] = P.get('honest_read', f"{md(t)} rule65 預設不掛，**0bp，累積維持 {ps['cumulative_weighted_bp']}bp**（{ps['days_evaluated']} 日）。{gtxt}"
                                              'Phase 3 起主帳無實單日記 0bp；績效比較看 shadow_ledger 與 amp_track。')

    # 影子帳
    sh = pnl['shadow_ledger']
    res = {}
    for o in sh['pending']:
        side, lim, a = o['side'], o['limit'], o['A_pts']
        r = shadow_fill(side, lim, a, o['s'], eO, eH, eL, eC)
        ent = {'report_date': o['report_date'], 'eval_date': t, 'side': side, 'limit': lim, 'A_pts': a, 'filled': r is not None}
        note = P.get(f'shadow_note_{side}')
        if r is None:
            ent.update(fill=None, stop=None, stop_hit=False, exit=None, pnl_pts=0.0, pnl_A=0.0,
                       note=note or f"{'低' if side == 'long' else '高'} {eL if side == 'long' else eH} 未達掛價 {lim}")
        else:
            ent['fill'] = r['fill']
            if P.get('shadow_fill_time_et', {}).get(side):
                ent['fill_time_et'] = P['shadow_fill_time_et'][side]
            ent.update(fill_type='gap_open' if r['gap'] else 'limit', stop=r['stop'], stop_hit=r['stop_hit'])
            if r['stop_hit'] and P.get('shadow_stop_time_et', {}).get(side):
                ent['stop_time_et'] = P['shadow_stop_time_et'][side]
            ent.update(exit=r['exit'], pnl_pts=r['pnl_pts'], pnl_A=r['pnl_A'],
                       note=note or f"成交 {r['fill']}（{'gap_open' if r['gap'] else 'limit'}）；{'觸停損' if r['stop_hit'] else '未觸停損'} {r['stop']}；出場 {r['exit']}")
        sh['entries'].append(ent)
        res[side] = ent
    sh['pending'] = [{'report_date': rep, 'basis_close': C, 'side': side, 'order': od, 'limit': lim, 'k': K_ENTRY, 's': S_STOP, 'A_pts': A_pts,
                      'stop_rule': f'成交價 {sg} s×A', 'exit': '隔日收盤'}
                     for side, od, lim, sg in (('long', 'limit_buy', LL, '−'), ('short', 'limit_sell', SL, '+'))]
    fl = [x for x in sh['entries'] if x['side'] == 'long' and x['filled']]
    fs = [x for x in sh['entries'] if x['side'] == 'short' and x['filled']]
    ss = sh['summary']
    ss.update(evaluated_days=len({x['report_date'] for x in sh['entries']}), filled_long=len(fl), filled_short=len(fs),
              mean_pnl_A_long=round(sum(x['pnl_A'] for x in fl) / len(fl), 3) if fl else None,
              mean_pnl_A_short=round(sum(x['pnl_A'] for x in fs) / len(fs), 3) if fs else None,
              cum_pnl_A=round(sum(x['pnl_A'] for x in sh['entries']), 3), as_of=rep)
    if gaps:
        ss['gap_days'] = ss.get('gap_days', []) + gaps

    # last_analysis 數值欄位
    def shadow_txt(side):
        x = res[side]
        lo_hi = ('低', eL) if side == 'long' else ('高', eH)
        if not x['filled']:
            return f"{x['limit']:.2f} 未成交（{lo_hi[0]} {lo_hi[1]:.2f}）"
        how = f"開盤跳空成交 {x['fill']:.2f}" if x['fill_type'] == 'gap_open' else f"{x['fill_time_et']} K 成交" if x.get('fill_time_et') else f"成交 {x['fill']:.2f}"
        if x['stop_hit']:
            when = f"{x['stop_time_et']} K " if x.get('stop_time_et') else ''
            return f"{x['limit']:.2f} → {how} → {when}觸停損 {x['stop']:.2f} ＝ {x['pnl_A']:+}A"
        return f"{x['limit']:.2f} → {how} → 未觸停損 {x['stop']:.2f} → 收盤 {eC:.2f} 平倉 ＝ {x['pnl_A']:+}A"

    la.update(trade_date=rep, data_basis=f'{day} US close', close=C, change_pct=chg, vix=td['vix'], pullback_prob=50,
              amplitude={'basis_date': day, 'target_session': rep, 'A_pct': A_pct, 'A_pts': A_pts, 'band_lo': BLO, 'band_hi': BHI,
                         'r0_ref_pct': amp['r0_rule27_ref_pct'], 'c': amp['c'], 'vol_pct_1y': amp['vol_pct_1y'],
                         'realized_vs_implied_63d': amp['realized_vs_implied_63d'], 'note': ''},
              direction={'prob': 50, 'bias': '中性', 'rule': None, 'note': 'Phase 3 恆 50；目前無方向規則達 rule63 門檻'})
    pr = la.setdefault('predictions', {})
    pr['geometry_A'] = {'A_pts': A_pts, 'rows': [{'k': k, 'long': round(C - k * A_pts, 1), 'short': round(C + k * A_pts, 1)} for k in (0.2, 0.4, 0.6, 0.8)],
                        'fill_rates_2014_2026': pr.get('geometry_A', {}).get('fill_rates_2014_2026')}
    pr['shadow_orders'] = {'long': {'limit': LL, 'stop': f'成交價 −0.5A（以掛價成交則 {round(LL - S_STOP * A_pts, 2)}）'},
                           'short': {'limit': SL, 'stop': f'成交價 +0.5A（以掛價成交則 {round(SL + S_STOP * A_pts, 2)}）'}}
    pr['no_trade'] = '本日無已核准的方向 edge → 不掛實單（rule65）'
    pr['strategies'] = {}
    la['backtest_prev'] = {'graded_date': t, 'predicted': '50 中性（不掛實單）',
                           'actual': f'收 {eC:,.2f}（{echg:+.2f}%，{act_dir}），開 {eO:,.2f}／高 {eH:,.2f}／低 {eL:,.2f}',
                           'grade': f'{g}（中性遇{DIR_ZH[act_dir]}）', 'brier': brier, 'rolling_direction_pct': s['rolling_direction_score_pct'],
                           'always_neutral_baseline_pct': base, 'mean_brier': b['mean_brier'], 'pnl_day_bp': 0.0, 'pnl_cum_bp': ps['cumulative_weighted_bp'],
                           'amp': {'A_pct': pa['A_pct'], 'actual_range_pct': act, 'log_err': le, 'r0_log_err': r0e, 'in_band': inb},
                           'shadow': {'long': shadow_txt('long'), 'short': shadow_txt('short')}, 'summary': ''}
    la['rule_status'] = {'as_of': rep, 'basis': f'{day} US close',
                         'rule63': f"主輸出：A {A_pct}%（{A_pts} 點）、50% 區間 {BLO}–{BHI}%、c {amp['c']}；方向 50、bias 中性",
                         'rule64': f'幾何以 A 表示：0.4A＝{round(0.4 * A_pts, 1)} 點、0.5A＝{round(0.5 * A_pts, 1)} 點',
                         'rule65': f'不掛實單；影子多 {LL:.2f}、影子空 {SL:.2f}（停損 ±0.5A＝{round(0.5 * A_pts, 1)} 點）',
                         'rule66': (f"振幅帳第 {len(es)} 筆：{md(t)} 實際 {act}% vs A {pa['A_pct']}%（log_err {le}、r0 {r0e}、{pos}）；"
                                    f"累計 mean_log_err {asum['mean_log_err']} vs r0 {asum['mean_r0_log_err']}、覆蓋 {asum['band_coverage_pct']}%"
                                    + (f"；{'、'.join(md(x) for x in gaps)} gap day 無預報" if gaps else '')),
                         'rule16': 'headline 恆 50（Phase 3）',
                         'rule17': f"系統 {s['rolling_direction_score_pct']}% vs 每天報中性 {base}%；Brier {b['mean_brier']} vs 0.25"}
    merge(la, nar.get('last_analysis', {}), SHALLOW)
    for k, v in nar.get('rule_candidates_append', {}).items():
        la['rule_candidates'][k] = la['rule_candidates'].get(k, '') + v

    report = {'trade_date': day, 'eval_date': t, 'report_date': rep, 'gap_days': gaps, 'A_pts': A_pts, 'shadow_pending': [LL, SL],
              'grade': g, 'brier': brier, 'rolling_direction_pct': s['rolling_direction_score_pct'], 'always_neutral_pct': base,
              'amp': {k: asum[k] for k in ('graded', 'mean_log_err', 'mean_r0_log_err', 'band_coverage_pct')},
              'shadow_today': {k: {kk: v.get(kk) for kk in ('filled', 'fill', 'stop', 'stop_hit', 'exit', 'pnl_A')} for k, v in res.items()},
              'shadow_summary': ss, 'narrative_keys': sorted(nar.get('last_analysis', {}))}
    return dict(zip(FILES, (tr, pnl, la))), report


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--docs', required=True)
    ap.add_argument('--today', required=True)
    ap.add_argument('--narrative')
    ap.add_argument('--report-date')
    ap.add_argument('--out')
    ap.add_argument('--report', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mech_report.txt'))
    a = ap.parse_args(argv)
    ledgers, report = build(a.docs, ld(a.today), ld(a.narrative) if a.narrative else None, a.report_date)
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        for f, o in ledgers.items():
            sv(os.path.join(a.out, f), o)
    report['wrote'] = a.out
    sv(a.report, report)


if __name__ == '__main__':
    main()
