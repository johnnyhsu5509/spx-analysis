"""NDX 每日記帳（Phase 3 機械部分）原型：ndx_track_record.json＋ndx_pnl_ledger.json。

對應每日手寫的 ndx_ledger_MMDD.py。差異：統計數字（graded／hits／days_evaluated／漂移基準歷史）一律從帳本重算，不手打。
影子單只有停損與收盤平倉、沒有目標價：價格必須先經過掛單價（或開盤跳空）才可能碰到停損，日線即可判定，不需 30 分 K 判序。
敘事（note、honest_read、成交／出場說明）由 --narrative 提供；沒給就用模板。
"""
import argparse, datetime, json, math, os

K_ENTRY, S_STOP, DIR_TH = 0.2, 0.5, 0.4


def ld(p):
    return json.load(open(p, encoding='utf-8'))


def sv(p, o):
    open(p, 'w', encoding='utf-8', newline='\n').write(json.dumps(o, ensure_ascii=False, indent=1) + '\n')


def next_bday(d):
    t = datetime.date.fromisoformat(d) + datetime.timedelta(days=1)
    while t.weekday() >= 5:
        t += datetime.timedelta(days=1)
    return t.isoformat()


def run(a):
    td = ld(a.today)
    assert td.get('symbol', 'NDX') == 'NDX', 'today_data 不是 NDX'
    nar = ld(a.narrative) if a.narrative else {}
    T, P = nar.get('track', {}), nar.get('pnl', {})
    tr = ld(os.path.join(a.docs, 'ndx_track_record.json'))
    pl = ld(os.path.join(a.docs, 'ndx_pnl_ledger.json'))
    la = ld(os.path.join(a.docs, 'ndx_last_analysis.json'))
    assert la.get('symbol') == 'NDX'

    day = td['trade_date']
    O, H, Lo, C, pc = td['open'], td['high'], td['low'], td['close'], td['prev_close']
    amp = td['amplitude']
    if not amp or amp.get('stale') or amp.get('as_of', day) != day:
        raise SystemExit('amplitude 缺或過期')
    A, A_pct = amp['amp_forecast_pts'], amp['amp_forecast_pct']
    rep = a.report_date or next_bday(day)
    pct = round((C / pc - 1) * 100, 2)
    act_dir = 'up' if pct >= DIR_TH else 'down' if pct <= -DIR_TH else 'flat'

    # ---- 方向帳
    e = tr['entries'][-1]
    assert e['grade'] == 'pending' and e['basis_date'] != day, '最後一筆不是待判定，或此收盤已判定過'
    if e['pullback_prob'] != 50:
        raise SystemExit('方向偏離 50：原型只處理 Phase 3 中性')
    g = 'hit' if act_dir == 'flat' else 'half'
    e.update(actual_date=day, actual_pct=pct, actual_dir=act_dir, grade=g,
             note=T.get('note', f'收 {C:,.2f}（{pct:+.2f}%）→ {act_dir}。Phase 3 方向恆 50 中性遇 {act_dir} → {g}'))
    graded = [x for x in tr['entries'] if x['grade'] in ('hit', 'half', 'miss')]
    s = tr['summary']
    n = len(graded)
    hits, half, miss = (sum(1 for x in graded if x['grade'] == k) for k in ('hit', 'half', 'miss'))
    s.update(as_of=rep, graded=n, hits=hits, half=half, miss=miss)
    s['rolling_direction_score_pct'] = round((hits + 0.5 * half) / n * 100, 1)
    b = s['brier']
    p = e['pullback_prob'] / 100
    outcome = None if act_dir == 'flat' else (1 if act_dir == 'down' else 0)
    b['per_entry'].append({'report_date': e['report_date'], 'p': p, 'outcome': outcome,
                           'brier': None if outcome is None else round((p - outcome) ** 2, 4)})
    vals = [x['brier'] for x in b['per_entry'] if x['brier'] is not None]
    b.update(as_of=rep, included=len(vals), mean_brier=round(sum(vals) / len(vals), 4))
    b['excluded_flat'] = sum(1 for x in b['per_entry'] if x['brier'] is None)
    flat = sum(1 for x in graded if x['actual_dir'] == 'flat')
    s['always_neutral_baseline_pct'] = round((flat + (n - flat) * 0.5) / n * 100, 1)
    s['sample_caveat'] = T.get('sample_caveat', f"n={n}。{s['rolling_direction_score_pct']}% ＝ ({hits} hit + {half} half×0.5 + {miss} miss) / {n}。always-neutral 基準 {s['always_neutral_baseline_pct']}%（依 audit_20261002 須並列）。Phase 3 起方向恆 50＝報法等同 always-neutral。")
    b['honest_read'] = T.get('brier_honest_read', f"mean brier **{b['mean_brier']:.4f}**（n={len(vals)}），貼近 0.25 基準、幾乎沒有資訊量。")
    tr['entries'].append({'report_date': rep, 'basis_close': C, 'basis_date': day, 'pullback_prob': 50, 'bias': '中性',
                          'actual_date': None, 'actual_pct': None, 'actual_dir': None, 'grade': 'pending', 'phase': 'Phase 3（方向恆 50）'})

    # ---- 振幅帳
    am = la['amplitude']
    assert am.get('basis_date') != day, '振幅預報的基準日就是今天，表示已判定過'
    act = round((H - Lo) / pc * 100, 3)
    le, r0e = round(abs(math.log(act / am['A_pct'])), 4), round(abs(math.log(act / am['r0_ref_pct'])), 4)
    inb = am['band_lo'] <= act <= am['band_hi']
    at = tr['amp_track']
    at['entries'].append({'report_date': e['report_date'], 'eval_date': day, 'A_pct': am['A_pct'], 'band_lo': am['band_lo'], 'band_hi': am['band_hi'],
                          'r0_ref_pct': am['r0_ref_pct'], 'actual_range_pct': act, 'log_err': le, 'r0_log_err': r0e, 'in_band': inb,
                          'note': T.get('amp_note', f"實際 {act:.3f}%（{H - Lo:.1f} 點）＝A 的 {act / am['A_pct']:.2f} 倍，{'落在' if inb else '超出'} 50% 區間")})
    ae = at['entries']
    at['summary'] = {'graded': len(ae), 'mean_log_err': round(sum(x['log_err'] for x in ae) / len(ae), 4),
                     'mean_r0_log_err': round(sum(x['r0_log_err'] for x in ae) / len(ae), 4),
                     'band_coverage_pct': round(sum(x['in_band'] for x in ae) / len(ae) * 100, 1),
                     'above_band': sum(x['actual_range_pct'] > x['band_hi'] for x in ae),
                     'below_band': sum(x['actual_range_pct'] < x['band_lo'] for x in ae), 'as_of': rep}

    # ---- P&L 主帳
    tp = pl['trades_pending']
    assert tp['report_date'] == e['report_date'], 'trades_pending 的日期對不上'
    if tp['trades']:
        raise SystemExit('有實單：原型不處理，請人工記帳')
    ps = pl['summary']
    pl['entries'].append({'report_date': e['report_date'], 'basis_close': pc, 'eval_date': day,
                          'eval_ohlc': {'open': O, 'high': H, 'low': Lo, 'close': C},
                          'rule50_check': 'Phase 3 預設休眠（rule57），無實單可判。', 'rule51_check': '無成交單，不需判序。', 'trades': [],
                          'day_weighted_bp': 0.0, 'day_note': P.get('day_note', f"Phase 3 預設不掛實單 → 當日 **0bp**。累積維持 **{ps['cumulative_weighted_bp']}bp**。")})
    ps['as_of'] = rep
    ps['days_evaluated'] += 1
    if 'honest_read' in P:
        ps['honest_read'] = P['honest_read']
    pl['trades_pending'] = {'report_date': rep, 'basis_close': C,
                            'eval_rule': f'用 {rep} 美股 NDX OHLC 判定。**Phase 3 預設休眠（rule57）**：無已核准方向規則 → 不掛實單；明日記 0bp 並更新 days_evaluated。',
                            'signal_A_pct': A_pct, 'signal_A_pts': A, 'trades': []}

    # ---- 影子帳
    sl = pl['shadow_ledger']
    pend = sl['pending']
    assert pend and all(x['report_date'] == e['report_date'] for x in pend)
    res = {}
    for o in pend:
        side, lim, Ap = o['side'], o['limit'], o['A_pts']
        filled = Lo <= lim if side == 'long' else H >= lim
        ent = {'report_date': o['report_date'], 'eval_date': day, 'side': side, 'limit': lim, 'filled': filled}
        if not filled:
            ent.update(fill=None, fill_type=P.get(f'fill_type_{side}', f"未成交（全日{'低' if side == 'long' else '高'} {Lo if side == 'long' else H:.2f} {'>' if side == 'long' else '<'} 掛單 {lim:.2f}）"),
                       stop=None, exit=None, exit_type=None, pnl_pts=None, pnl_A=None, A_pts=Ap)
        else:
            fill = min(lim, O) if side == 'long' else max(lim, O)
            gap = fill != lim
            stop = round(fill - S_STOP * Ap, 2) if side == 'long' else round(fill + S_STOP * Ap, 2)
            hit = Lo <= stop if side == 'long' else H >= stop
            ex = stop if hit else C
            pts = round(ex - fill, 2) if side == 'long' else round(fill - ex, 2)
            dflt_fill = f"開盤跳空成交（開 {O:.2f} {'<' if side == 'long' else '>'} 掛單 {lim:.2f}）" if gap else '盤中成交'
            dflt_exit = '停損出場' if hit else f"隔日收盤平倉（{'低' if side == 'long' else '高'} {Lo if side == 'long' else H} 未觸停損 {stop}）"
            ent.update(fill=fill, fill_type=P.get(f'fill_type_{side}', dflt_fill), stop=stop, exit=ex,
                       exit_type=P.get(f'exit_type_{side}', dflt_exit), pnl_pts=pts, pnl_A=round(pts / Ap, 3), A_pts=Ap)
        sl['entries'].append(ent)
        res[side] = ent
    ents = sl['entries']
    fl = [x for x in ents if x['side'] == 'long' and x['filled']]
    fs = [x for x in ents if x['side'] == 'short' and x['filled']]
    nl, ns = sum(x['side'] == 'long' for x in ents), sum(x['side'] == 'short' for x in ents)
    days = sorted({x['report_date'] for x in ents})
    pe = {x['report_date']: x for x in pl['entries'] if 'eval_ohlc' in x}
    ap = {x['report_date']: x['A_pts'] for x in ents}
    dr = [(d, round((pe[d]['eval_ohlc']['close'] - pe[d]['basis_close']) / ap[d], 3)) for d in days]
    dm = sum(v for _, v in dr) / len(dr)
    sl['summary'] = {'days': len(days), 'filled_long': len(fl), 'filled_short': len(fs),
                     'mean_pnl_A_long': round(sum(x['pnl_A'] for x in fl) / len(fl), 3) if fl else None,
                     'mean_pnl_A_short': round(sum(x['pnl_A'] for x in fs) / len(fs), 3) if fs else None,
                     'fill_rate_long_pct': round(len(fl) / nl * 100, 1), 'fill_rate_short_pct': round(len(fs) / ns * 100, 1),
                     'drift_bench_mean_A': round(dm, 3),
                     'drift_bench_note': '同期『收盤買、隔日收盤賣』每天平均報酬（以 A 計）：' + '、'.join(f"{d[5:].replace('-', '/').lstrip('0')} {v:+.3f} A" for d, v in dr) + f'，平均 {dm:.3f} A',
                     'as_of': rep}
    sl['pending'] = [
        {'report_date': rep, 'basis_close': C, 'side': 'long', 'order': 'limit_buy', 'limit': round(C - K_ENTRY * A, 2), 'k': K_ENTRY, 's': S_STOP, 'A_pts': A, 'stop_rule': '成交價 − s×A', 'exit': '隔日收盤'},
        {'report_date': rep, 'basis_close': C, 'side': 'short', 'order': 'limit_sell', 'limit': round(C + K_ENTRY * A, 2), 'k': K_ENTRY, 's': S_STOP, 'A_pts': A, 'stop_rule': '成交價 + s×A', 'exit': '隔日收盤'}]

    rpt = {'trade_date': day, 'report_date': rep, 'pct': pct, 'dir': act_dir, 'grade': g, 'score': s['rolling_direction_score_pct'],
           'baseline': s['always_neutral_baseline_pct'], 'brier': b['mean_brier'], 'amp': at['summary'], 'shadow_today': res,
           'shadow_summary': sl['summary'], 'pending': [x['limit'] for x in sl['pending']], 'wrote': bool(a.out)}
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        sv(os.path.join(a.out, 'ndx_track_record.json'), tr)
        sv(os.path.join(a.out, 'ndx_pnl_ledger.json'), pl)
    open(a.report, 'w', encoding='utf-8').write(json.dumps(rpt, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    ap_ = argparse.ArgumentParser()
    ap_.add_argument('--docs', required=True)
    ap_.add_argument('--today', required=True)
    ap_.add_argument('--narrative')
    ap_.add_argument('--report-date')
    ap_.add_argument('--out')
    ap_.add_argument('--report', default='ndx_mech_report.txt')
    run(ap_.parse_args())
