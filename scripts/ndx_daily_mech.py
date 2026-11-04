"""NDX 每日記帳（Phase 3 休眠期）：ndx_track_record.json＋ndx_pnl_ledger.json 的數值欄位由固定公式產生，敘事由 --narrative 提供。

  python scripts/ndx_daily_mech.py --docs docs --today scripts/ndx_today_data.txt --narrative narrative_MMDD.json [--out DIR] [--report scripts/ndx_mech_report.txt]

統計數字（graded／hits／days_evaluated／漂移基準歷史）一律從帳本重算。影子單只有停損與收盤平倉，日線即可判定。
不加 --out 只寫 --report，不寫任何帳本。ndx_last_analysis.json 由 ndx_last_mech.py 接著產生。
"""
import argparse
import os

from mech_lib import eval_session, ld, log_err, md, mean_hu, next_bday, shadow_fill, sv

K_ENTRY, S_STOP, DIR_TH = 0.2, 0.5, 0.4
FILES = ('ndx_track_record.json', 'ndx_pnl_ledger.json')


def build(docs, td, nar=None, report_date=None):
    nar = nar or {}
    T, P = nar.get('track', {}), nar.get('pnl', {})
    if td.get('symbol', 'NDX') != 'NDX':
        raise SystemExit('today_data 不是 NDX')
    tr, pl = (ld(os.path.join(docs, f)) for f in FILES)
    la = ld(os.path.join(docs, 'ndx_last_analysis.json'))
    day = td['trade_date']
    if la.get('data_basis', '').startswith(day):
        raise SystemExit(f'DUPLICATE：ndx_last_analysis 已以 {day} 收盤分析過')
    amp = td.get('amplitude')
    if not amp or amp.get('stale') or amp.get('as_of', day) != day:
        raise SystemExit('amplitude 缺或過期：照 SKILL 寫「振幅資料缺」，本腳本不處理')
    A, A_pct, C = amp['amp_forecast_pts'], amp['amp_forecast_pct'], td['close']
    rep = report_date or next_bday(day)

    e = tr['entries'][-1]
    if e['grade'] != 'pending':
        raise SystemExit(f"ndx_track_record 最後一筆不是 pending：{e['report_date']}")
    if e['pullback_prob'] != 50:
        raise SystemExit('方向偏離 50：只支援 Phase 3 中性，請人工記帳')
    t = e['report_date']
    am = la['amplitude']
    if am['target_session'] != t:
        raise SystemExit(f"振幅預報目標日 {am['target_session']} 與待判定預測 {t} 對不上")
    tp = pl['trades_pending']
    if tp['report_date'] != t:
        raise SystemExit(f"trades_pending 的日期 {tp['report_date']} 與待判定預測 {t} 對不上")
    if tp['trades']:
        raise SystemExit('有實單：本腳本不處理實單判定，請人工記帳')
    if len(pl['shadow_ledger']['pending']) != 2 or any(x['report_date'] != t for x in pl['shadow_ledger']['pending']):
        raise SystemExit('影子單 pending 不是兩張、或 report_date 對不上')
    E, gaps = eval_session(td, t)
    O, H, Lo, eC, pc = E['o'], E['h'], E['l'], E['c'], E['pc']
    pct = round((eC / pc - 1) * 100, 3)
    act_dir = 'up' if pct >= DIR_TH else 'down' if pct <= -DIR_TH else 'flat'

    # 方向帳＋Brier
    g = 'hit' if act_dir == 'flat' else 'half'
    e.update(actual_date=t, actual_pct=pct, actual_dir=act_dir, grade=g,
             note=T.get('note', f'收 {eC:,.2f}（{pct:+.2f}%）→ {act_dir}。Phase 3 方向恆 50 中性遇 {act_dir} → {g}'))
    graded = [x for x in tr['entries'] if x['grade'] in ('hit', 'half', 'miss')]
    s = tr['summary']
    n = len(graded)
    hits, half, miss = (sum(x['grade'] == k for x in graded) for k in ('hit', 'half', 'miss'))
    s.update(as_of=rep, graded=n, hits=hits, half=half, miss=miss)
    s['rolling_direction_score_pct'] = round((hits + 0.5 * half) / n * 100, 1)
    if gaps:
        s['gap_days'] = s.get('gap_days', []) + [x for x in gaps if x not in s.get('gap_days', [])]
    b = s['brier']
    p = e['pullback_prob'] / 100
    outcome = None if act_dir == 'flat' else (1 if act_dir == 'down' else 0)
    b['per_entry'].append({'report_date': t, 'p': p, 'outcome': outcome, 'brier': None if outcome is None else round((p - outcome) ** 2, 4)})
    vals = [x['brier'] for x in b['per_entry'] if x['brier'] is not None]
    b.update(as_of=rep, included=len(vals), excluded_flat=len(b['per_entry']) - len(vals), mean_brier=round(sum(vals) / len(vals), 4))
    flat = sum(x['actual_dir'] == 'flat' for x in graded)
    s['always_neutral_baseline_pct'] = round((flat + (n - flat) * 0.5) / n * 100, 1)
    s['sample_caveat'] = T.get('sample_caveat', f"n={n}。{s['rolling_direction_score_pct']}% ＝ ({hits} hit + {half} half×0.5 + {miss} miss) / {n}。"
                                                f"always-neutral 基準 {s['always_neutral_baseline_pct']}%（依 audit_20261002 須並列）。Phase 3 起方向恆 50＝報法等同 always-neutral。")
    b['honest_read'] = T.get('brier_honest_read', f"mean brier **{b['mean_brier']:.4f}**（n={len(vals)}），貼近 0.25 基準、幾乎沒有資訊量。")
    for x in gaps:
        s[f"gap_note_{x.replace('-', '')}"] = T.get('gap_note', f'**{md(x)} 為 gap day**：前一收盤未產出報告，{md(x)} 無預測可判，不計入任何統計。')
    tr['entries'].append({'report_date': rep, 'basis_close': C, 'basis_date': day, 'pullback_prob': 50, 'bias': '中性',
                          'actual_date': None, 'actual_pct': None, 'actual_dir': None, 'grade': 'pending', 'phase': 'Phase 3（方向恆 50）'})

    # 振幅帳
    raw = (H - Lo) / pc * 100
    act = round(raw, 3)
    le, r0e = log_err(act, am['A_pct']), log_err(act, am['r0_ref_pct'])
    inb = am['band_lo'] <= act <= am['band_hi']
    pos = '落在' if inb else '低於' if act < am['band_lo'] else '高於'
    at = tr['amp_track']
    at['entries'].append({'report_date': t, 'eval_date': t, 'A_pct': am['A_pct'], 'band_lo': am['band_lo'], 'band_hi': am['band_hi'],
                          'r0_ref_pct': am['r0_ref_pct'], 'actual_range_pct': act, 'log_err': le, 'r0_log_err': r0e, 'in_band': inb,
                          'note': T.get('amp_note', f"實際 {act:.3f}%（{H - Lo:.1f} 點）＝A 的 {act / am['A_pct']:.2f} 倍，{pos} 50% 區間")})
    ae = at['entries']
    asum = at['summary']
    asum.update(graded=len(ae), mean_log_err=round(sum(x['log_err'] for x in ae) / len(ae), 4),
                mean_r0_log_err=round(sum(x['r0_log_err'] for x in ae) / len(ae), 4),
                band_coverage_pct=round(sum(x['in_band'] for x in ae) / len(ae) * 100, 1),
                above_band=sum(x['actual_range_pct'] > x['band_hi'] for x in ae),
                below_band=sum(x['actual_range_pct'] < x['band_lo'] for x in ae), as_of=rep)
    if gaps:
        asum['gap_days'] = asum.get('gap_days', []) + gaps

    # P&L 主帳（無實單日）
    ps = pl['summary']
    pl['entries'].append({'report_date': t, 'basis_close': pc, 'eval_date': t, 'eval_ohlc': {'open': O, 'high': H, 'low': Lo, 'close': eC},
                          'rule50_check': 'Phase 3 預設休眠（rule57），無實單可判。', 'rule51_check': '無成交單，不需判序。', 'trades': [],
                          'day_weighted_bp': 0.0, 'day_note': P.get('day_note', f"Phase 3 預設不掛實單 → 當日 **0bp**。累積維持 **{ps['cumulative_weighted_bp']}bp**。")})
    ps['as_of'] = rep
    ps['days_evaluated'] += 1
    if gaps:
        ps['gap_days'] = ps.get('gap_days', []) + [x for x in gaps if x not in ps.get('gap_days', [])]
    if 'honest_read' in P:
        ps['honest_read'] = P['honest_read']
    for x in gaps:
        pl[f"gap_note_{x.replace('-', '_')}"] = P.get('gap_note', f'前一收盤未產出報告，{md(x)} 無策略或影子單，不回補。')
    pl['trades_pending'] = {'report_date': rep, 'basis_close': C,
                            'eval_rule': f'用 {rep} 美股 NDX OHLC 判定。**Phase 3 預設休眠（rule57）**：無已核准方向規則 → 不掛實單；明日記 0bp 並更新 days_evaluated。',
                            'signal_A_pct': A_pct, 'signal_A_pts': A, 'trades': []}

    # 影子帳
    sl = pl['shadow_ledger']
    res = {}
    for o in sl['pending']:
        side, lim, Ap = o['side'], o['limit'], o['A_pts']
        r = shadow_fill(side, lim, Ap, o['s'], O, H, Lo, eC)
        lo_hi = ('低', Lo, '>') if side == 'long' else ('高', H, '<')
        ent = {'report_date': t, 'eval_date': t, 'side': side, 'limit': lim, 'filled': r is not None}
        if r is None:
            ent.update(fill=None, fill_type=P.get(f'fill_type_{side}', f'未成交（全日{lo_hi[0]} {lo_hi[1]:.2f} {lo_hi[2]} 掛單 {lim:.2f}）'),
                       stop=None, exit=None, exit_type=None, pnl_pts=None, pnl_A=None, A_pts=Ap)
        else:
            dflt_fill = f"開盤跳空成交（開 {O:.2f} {'<' if side == 'long' else '>'} 掛單 {lim:.2f}）" if r['gap'] else '盤中成交'
            dflt_exit = '停損出場' if r['stop_hit'] else f"收盤平倉（停損 {r['stop']:.2f} 未觸，全日{lo_hi[0]} {lo_hi[1]:.2f}）"
            ent.update(fill=r['fill'], fill_type=P.get(f'fill_type_{side}', dflt_fill), stop=r['stop'], exit=r['exit'],
                       exit_type=P.get(f'exit_type_{side}', dflt_exit), pnl_pts=r['pnl_pts'], pnl_A=r['pnl_A'], A_pts=Ap)
        sl['entries'].append(ent)
        res[side] = ent
    ents = sl['entries']
    fl = [x for x in ents if x['side'] == 'long' and x['filled']]
    fs = [x for x in ents if x['side'] == 'short' and x['filled']]
    nl, ns = sum(x['side'] == 'long' for x in ents), sum(x['side'] == 'short' for x in ents)
    days = sorted({x['report_date'] for x in ents})
    pe = {x['report_date']: x for x in pl['entries'] if 'eval_ohlc' in x}
    apts = {x['report_date']: x['A_pts'] for x in ents}
    dr = [(d, round((pe[d]['eval_ohlc']['close'] - pe[d]['basis_close']) / apts[d], 3)) for d in days]
    dm = sum(v for _, v in dr) / len(dr)
    ss = sl['summary']
    ss.update(days=len(days), filled_long=len(fl), filled_short=len(fs),
              mean_pnl_A_long=mean_hu([x['pnl_A'] for x in fl]) if fl else None,
              mean_pnl_A_short=mean_hu([x['pnl_A'] for x in fs]) if fs else None,
              fill_rate_long_pct=round(len(fl) / nl * 100, 1), fill_rate_short_pct=round(len(fs) / ns * 100, 1),
              drift_bench_mean_A=round(dm, 3),
              drift_bench_note='同期『收盤買、隔日收盤賣』每天平均報酬（以 A 計）：' + '、'.join(f"{d[5:].replace('-', '/').lstrip('0')} {v:+.3f}" for d, v in dr) + f'，平均 {dm:.3f} A',
              as_of=rep)
    if gaps:
        ss['gap_days'] = ss.get('gap_days', []) + gaps
    sl['pending'] = [{'report_date': rep, 'basis_close': C, 'side': side, 'order': od, 'limit': round(C + sg * K_ENTRY * A, 2), 'k': K_ENTRY, 's': S_STOP,
                      'A_pts': A, 'stop_rule': f"成交價 {'−' if sg < 0 else '+'} s×A", 'exit': '隔日收盤'}
                     for side, od, sg in (('long', 'limit_buy', -1), ('short', 'limit_sell', 1))]

    report = {'trade_date': day, 'eval_date': t, 'report_date': rep, 'gap_days': gaps, 'pct': pct, 'dir': act_dir, 'grade': g,
              'score': s['rolling_direction_score_pct'], 'baseline': s['always_neutral_baseline_pct'], 'mean_brier': b['mean_brier'],
              'amp': {k: asum[k] for k in ('graded', 'mean_log_err', 'mean_r0_log_err', 'band_coverage_pct')},
              'shadow_today': {k: {kk: v.get(kk) for kk in ('filled', 'fill', 'stop', 'exit', 'pnl_A')} for k, v in res.items()},
              'shadow_summary': {k: ss[k] for k in ('days', 'filled_long', 'filled_short', 'drift_bench_mean_A')}, 'pending': [x['limit'] for x in sl['pending']]}
    return dict(zip(FILES, (tr, pl))), report


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--docs', required=True)
    ap.add_argument('--today', required=True)
    ap.add_argument('--narrative')
    ap.add_argument('--report-date')
    ap.add_argument('--out')
    ap.add_argument('--report', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ndx_mech_report.txt'))
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
