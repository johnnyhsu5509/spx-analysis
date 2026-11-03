"""SPX 每日記帳（Phase 3 機械部分）原型。

把每日 spx_update_MMDD.py 裡「固定公式」的部分收成一支參數化腳本：
方向評分、Brier、振幅帳、P&L 主帳（無實單日）、影子帳成交與停損、統計摘要、
last_analysis 的數值欄位與 rule63/64/65/66/16/17 狀態行。
敘事文字（bias、grade_note、news_check、predictions…）由 --narrative 的 JSON 提供，深度合併進去。

用法：
  python3 spx_daily_mech.py --docs ../docs --today today_data.txt --narrative narrative_1022.json --out OUTDIR
  不加 --out 時只寫 mech_report.txt，不寫任何帳本。--out 指向 docs 才等於正式寫入。
"""
import argparse, datetime, json, math, os

K_ENTRY, S_STOP = 0.4, 0.5


def ld(p):
    return json.load(open(p, encoding='utf-8'))


def sv(p, o):
    json.dump(o, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


SHALLOW_MERGE = ('amplitude', 'predictions', 'backtest_prev', 'rule_status')
DIR_LABEL = {'up': '漲', 'down': '跌', 'flat': '平'}


def merge(dst, src):
    for k, v in src.items():
        if k in SHALLOW_MERGE and isinstance(v, dict) and isinstance(dst.get(k), dict):
            dst[k].update(v)
        else:
            dst[k] = v
    return dst


def next_bday(d):
    t = datetime.date.fromisoformat(d) + datetime.timedelta(days=1)
    while t.weekday() >= 5:
        t += datetime.timedelta(days=1)
    return t.isoformat()


def direction(chg):
    return 'up' if chg >= 0.3 else 'down' if chg <= -0.3 else 'flat'


def grade(prob, actual):
    if prob != 50:
        raise SystemExit(f'pullback_prob={prob}：Phase 3 原型只支援方向 50（中性），偏離 50 需要人工記帳')
    return 'hit' if actual == 'flat' else 'half'


def shadow_fill(order, O, H, Lo, C):
    lim, a = order['limit'], order['A_pts']
    if order['side'] == 'long':
        if Lo > lim:
            return None
        fill = min(lim, O)
        stop = round(fill - S_STOP * a, 2)
        hit = Lo <= stop
        exit_ = stop if hit else C
        pts = round(exit_ - fill, 2)
    else:
        if H < lim:
            return None
        fill = max(lim, O)
        stop = round(fill + S_STOP * a, 2)
        hit = H >= stop
        exit_ = stop if hit else C
        pts = round(fill - exit_, 2)
    return {'fill': fill, 'fill_type': 'limit' if fill == lim else 'gap_open', 'stop': stop,
            'stop_hit': hit, 'exit': exit_, 'pnl_pts': pts, 'pnl_A': round(pts / a, 3)}


def run(a):
    td = ld(a.today)
    nar = ld(a.narrative) if a.narrative else {}
    tr = ld(os.path.join(a.docs, 'track_record.json'))
    pnl = ld(os.path.join(a.docs, 'pnl_ledger.json'))
    la = ld(os.path.join(a.docs, 'last_analysis.json'))

    day = td['trade_date']
    if la.get('data_basis', '').startswith(day):
        raise SystemExit(f'DUPLICATE：last_analysis 已以 {day} 收盤分析過')
    O, H, Lo, C, PC = td['open'], td['high'], td['low'], td['close'], td['prev_close']
    chg = td['change_pct']
    amp = td['amplitude']
    if not amp or amp.get('stale') or amp.get('as_of') != day:
        raise SystemExit('amplitude 缺或過期：照 SKILL 寫「振幅資料缺」，本腳本不處理')
    A_pct = amp['amp_forecast_pct']
    A_pts = round(A_pct * C / 100, 2)
    BLO, BHI = amp['band_50_pct']
    rep = a.report_date or next_bday(day)
    LL, SL = round(C - K_ENTRY * A_pts, 2), round(C + K_ENTRY * A_pts, 2)
    N = nar.get('track', {})
    P = nar.get('pnl', {})

    # ---- 方向帳＋Brier
    e = tr['entries'][-1]
    assert e['grade'] == 'pending', f"最後一筆不是 pending：{e['report_date']}"
    act_dir = direction(chg)
    g = grade(e['pullback_prob'], act_dir)
    e.update({'actual_date': day, 'actual_pct': chg, 'actual_dir': act_dir, 'grade': g,
              'grade_note': N.get('grade_note', f'實際 {chg:+.2f}%（收 {C:,.2f}）＝{act_dir}；方向 50「中性」→ {g}')})
    tr['entries'].append({'report_date': rep, 'basis_close': C, 'pullback_prob': 50,
                          'bias': N.get('bias', f'中性 50（方向無 edge，rule63／rule16）。基準 {day} 收 {C:,.2f}（{chg:+.2f}%）'),
                          'actual_date': f'{rep}(pending)', 'actual_pct': None, 'actual_dir': None, 'grade': 'pending'})
    s = tr['summary']
    s['graded'] += 1
    s[{'hit': 'hits', 'half': 'half', 'miss': 'miss'}[g]] += 1
    s['as_of'] = rep
    s['rolling_direction_score_pct'] = round((s['hits'] + 0.5 * s['half']) / s['graded'] * 100, 1)
    b = s['brier']
    p = e['pullback_prob'] / 100
    if act_dir == 'flat':
        b['excluded_flat'] += 1
        brier = None
    else:
        brier = round((p - (1 if act_dir == 'down' else 0)) ** 2, 4)
        b['per_entry'].append({'report_date': e['report_date'], 'p': p, 'outcome': 1 if act_dir == 'down' else 0, 'brier': brier})
    b['included'] = len(b['per_entry'])
    b['as_of'] = rep
    b['mean_brier'] = round(sum(x['brier'] for x in b['per_entry']) / len(b['per_entry']), 4)
    btxt = '排除（flat）' if brier is None else f"{brier}（Phase 3 恆值）" if p == 0.5 else brier
    b['note_latest'] = f"{e['report_date']}：方向 50 中性遇 {chg:+.2f}%＝{act_dir}（{g}），Brier {btxt}。mean_brier {b['mean_brier']}（{b['included']} 筆）"
    n, flat = s['graded'], b['excluded_flat']
    base = round((flat + (n - flat) * 0.5) / n * 100, 1)
    s[f"always_neutral_baseline_{rep.replace('-', '')}"] = f"依 rule17 並列：每天報中性基準 {base}%（{n} 筆，flat {flat}）vs 系統 {s['rolling_direction_score_pct']}%；Brier {b['mean_brier']} vs 0.25"

    # ---- 振幅帳
    pa = la['amplitude']
    assert pa['target_session'] == day, f"上一份振幅預報的目標日 {pa['target_session']} ≠ {day}"
    act = round((H - Lo) / PC * 100, 4)
    le = round(abs(math.log(act / pa['A_pct'])), 4)
    r0e = round(abs(math.log(act / pa['r0_ref_pct'])), 4)
    inb = pa['band_lo'] <= act <= pa['band_hi']
    at = tr['amp_track']
    at['entries'].append({'report_date': e['report_date'], 'basis_date': pa['basis_date'], 'eval_date': day,
                          'A_pct': pa['A_pct'], 'band_lo': pa['band_lo'], 'band_hi': pa['band_hi'], 'r0_ref_pct': pa['r0_ref_pct'],
                          'actual_range_pct': act, 'log_err': le, 'r0_log_err': r0e, 'in_band': inb,
                          'note': N.get('amp_note', f"實際 {act:.2f}% 為 A 的 {act / pa['A_pct']:.2f} 倍，{'落在' if inb else '超出'} 50% 區間")})
    es = at['entries']
    at['summary'] = {'graded': len(es), 'mean_log_err': round(sum(x['log_err'] for x in es) / len(es), 4),
                     'mean_r0_log_err': round(sum(x['r0_log_err'] for x in es) / len(es), 4),
                     'band_coverage_pct': round(sum(1 for x in es if x['in_band']) / len(es) * 100, 1), 'as_of': rep,
                     'note': f'樣本 {len(es)} 筆，無統計意義；60 筆後依 rule66 判定'}

    # ---- P&L 主帳（無實單日）
    pe = pnl['entries'][-1]
    if pe['trades_pending']:
        raise SystemExit('有實單 trades_pending：原型不處理實單判定，請人工記帳')
    ps = pnl['summary']
    pe.update({'eval_date': day, 'ohlc': {'o': O, 'h': H, 'l': Lo, 'c': C}, 'results': [], 'day_weighted_bp': 0.0,
               'day_note': P.get('day_note', f"**0bp（rule65 預設不掛），累積維持 {ps['cumulative_weighted_bp']}bp。**discretionary_log 不新增")})
    pnl['entries'].append({'report_date': rep, 'eval_date': f'pending({rep} US close)', 'basis_close': C,
                           'thresholds': {'A_pct': A_pct, 'A_pts': A_pts, 'band_50_pct': [BLO, BHI], 'note': 'Phase 3：掛單幾何以 A 為單位（rule64）'},
                           'trades_pending': [],
                           'structure_note': '**Phase 3 預設休眠（rule65）：本日無已核准的方向 edge → 不掛實單。**影子單兩張另記 shadow_ledger'})
    ps['as_of'] = rep
    ps['days_evaluated'] += 1
    ps['honest_read'] = P.get('honest_read', f"{day[5:].replace('-', '/')} rule65 預設不掛，**0bp，累積維持 {ps['cumulative_weighted_bp']}bp**（{ps['days_evaluated']} 日）。Phase 3 起主帳無實單日記 0bp；績效比較看 shadow_ledger 與 amp_track。")

    # ---- 影子帳
    sh = pnl['shadow_ledger']
    pend = sh['pending']
    assert pend and all(x['report_date'] == e['report_date'] for x in pend), '影子單 pending 的 report_date 對不上'
    shadow_res = {}
    for o in pend:
        r = shadow_fill(o, O, H, Lo, C)
        note = P.get(f"shadow_note_{o['side']}")
        if r is None:
            ent = {'report_date': o['report_date'], 'eval_date': day, 'side': o['side'], 'limit': o['limit'], 'A_pts': o['A_pts'],
                   'filled': False, 'fill': None, 'stop': None, 'stop_hit': False, 'exit': None, 'pnl_pts': 0.0, 'pnl_A': 0.0,
                   'note': note or (f"低 {Lo} 未達掛價 {o['limit']}" if o['side'] == 'long' else f"高 {H} 未達掛價 {o['limit']}")}
        else:
            ent = {'report_date': o['report_date'], 'eval_date': day, 'side': o['side'], 'limit': o['limit'], 'A_pts': o['A_pts'], 'filled': True,
                   'fill': r['fill']}
            if P.get('shadow_fill_time_et', {}).get(o['side']):
                ent['fill_time_et'] = P['shadow_fill_time_et'][o['side']]
            ent.update({'fill_type': r['fill_type'], 'stop': r['stop'], 'stop_hit': r['stop_hit'], 'exit': r['exit'],
                        'pnl_pts': r['pnl_pts'], 'pnl_A': r['pnl_A'],
                        'note': note or f"成交 {r['fill']}（{r['fill_type']}）；{'觸停損' if r['stop_hit'] else '未觸停損'} {r['stop']}；出場 {r['exit']}"})
        sh['entries'].append(ent)
        shadow_res[o['side']] = ent
    sh['pending'] = [
        {'report_date': rep, 'basis_close': C, 'side': 'long', 'order': 'limit_buy', 'limit': LL, 'k': K_ENTRY, 's': S_STOP, 'A_pts': A_pts, 'stop_rule': '成交價 − s×A', 'exit': '隔日收盤'},
        {'report_date': rep, 'basis_close': C, 'side': 'short', 'order': 'limit_sell', 'limit': SL, 'k': K_ENTRY, 's': S_STOP, 'A_pts': A_pts, 'stop_rule': '成交價 + s×A', 'exit': '隔日收盤'}]
    fL = [x for x in sh['entries'] if x['side'] == 'long' and x['filled']]
    fS = [x for x in sh['entries'] if x['side'] == 'short' and x['filled']]
    sh['summary'] = {'evaluated_days': len({x['report_date'] for x in sh['entries']}), 'filled_long': len(fL), 'filled_short': len(fS),
                     'mean_pnl_A_long': round(sum(x['pnl_A'] for x in fL) / len(fL), 3) if fL else None,
                     'mean_pnl_A_short': round(sum(x['pnl_A'] for x in fS) / len(fS), 3) if fS else None,
                     'cum_pnl_A': round(sum(x['pnl_A'] for x in sh['entries']), 3), 'as_of': rep}

    # ---- last_analysis 數值欄位
    def shadow_txt(side):
        x = shadow_res[side]
        if not x['filled']:
            return f"{x['limit']} 未成交（{'低 ' + str(Lo) if side == 'long' else '高 ' + str(H)}）"
        if x['fill_type'] == 'gap_open':
            at_ = f"跳空成交於開盤 {x['fill']}"
        else:
            at_ = f"於 {x['fill_time_et']} 成交" if x.get('fill_time_et') else f"成交 {x['fill']}"
        if x['stop_hit']:
            return f"{x['limit']} {at_} → 停損 {x['stop']} 觸及 → 停損出場 {x['pnl_A']:+}A"
        ext, gap = ('低', round(Lo - x['stop'], 2)) if side == 'long' else ('高', round(x['stop'] - H, 2))
        return f"{x['limit']} {at_} → 停損 {x['stop']} 未觸（{ext} {Lo if side == 'long' else H}，差 {gap} 點）→ 收盤平倉 {x['pnl_A']:+}A"
    geom = {'A_pts': A_pts, 'rows': [{'k': k, 'long': round(C - k * A_pts, 1), 'short': round(C + k * A_pts, 1)} for k in (0.2, 0.4, 0.6, 0.8)],
            'fill_rates_2014_2026': la.get('predictions', {}).get('geometry_A', {}).get('fill_rates_2014_2026')}
    la.update({'trade_date': rep, 'data_basis': f'{day} US close', 'close': C, 'change_pct': chg, 'vix': td['vix'], 'pullback_prob': 50,
               'amplitude': {'basis_date': day, 'target_session': rep, 'A_pct': A_pct, 'A_pts': A_pts, 'band_lo': BLO, 'band_hi': BHI,
                             'r0_ref_pct': amp['r0_rule27_ref_pct'], 'c': amp['c'], 'vol_pct_1y': amp['vol_pct_1y'],
                             'realized_vs_implied_63d': amp['realized_vs_implied_63d'], 'note': ''},
               'direction': {'prob': 50, 'bias': '中性', 'rule': None, 'note': 'Phase 3 恆 50；目前無方向規則達 rule63 門檻'}})
    pr = la.setdefault('predictions', {})
    pr['geometry_A'] = geom
    pr['shadow_orders'] = {'long': {'limit': LL, 'stop': f'成交價 −0.5A（以掛價成交則 {round(LL - 0.5 * A_pts, 2)}）'},
                           'short': {'limit': SL, 'stop': f'成交價 +0.5A（以掛價成交則 {round(SL + 0.5 * A_pts, 2)}）'}}
    pr['no_trade'] = '本日無已核准的方向 edge → 不掛實單（rule65）'
    pr['strategies'] = {}
    la['backtest_prev'] = {'graded_date': day, 'predicted': '50 中性（不掛實單）',
                           'actual': f'收 {C:,.2f}（{chg:+.2f}%，{act_dir}），開 {O:,.2f}／高 {H:,.2f}／低 {Lo:,.2f}',
                           'grade': f"{g}（中性遇{DIR_LABEL[act_dir]}）", 'brier': brier, 'rolling_direction_pct': s['rolling_direction_score_pct'], 'always_neutral_baseline_pct': base,
                           'mean_brier': b['mean_brier'], 'pnl_day_bp': 0.0, 'pnl_cum_bp': ps['cumulative_weighted_bp'],
                           'amp': {'A_pct': pa['A_pct'], 'actual_range_pct': act, 'log_err': le, 'r0_log_err': r0e, 'in_band': inb},
                           'shadow': {'long': shadow_txt('long'), 'short': shadow_txt('short')}, 'summary': ''}
    la['rule_status'] = {'as_of': rep, 'basis': f'{day} US close',
                         'rule63': f"主輸出：A {A_pct}%（{A_pts} 點）、50% 區間 {BLO}–{BHI}%、c {amp['c']}；方向 50、bias 中性",
                         'rule64': f'幾何以 A 表示：0.4A＝{round(0.4 * A_pts, 1)} 點、0.5A＝{round(0.5 * A_pts, 1)} 點',
                         'rule65': f'不掛實單；影子多 {LL}、影子空 {SL}（停損 ±0.5A＝{round(0.5 * A_pts, 1)} 點）',
                         'rule66': f"振幅帳第 {len(es)} 筆：{day[5:].replace('-', '/')} 實際 {act}% vs A {pa['A_pct']}%（log_err {le}、r0 {r0e}、{'區間內' if inb else '區間外'}）；累計 mean_log_err {at['summary']['mean_log_err']} vs r0 {at['summary']['mean_r0_log_err']}、覆蓋 {at['summary']['band_coverage_pct']}%",
                         'rule16': 'headline 恆 50（Phase 3）',
                         'rule17': f"系統 {s['rolling_direction_score_pct']}% vs 每天報中性 {base}%；Brier {b['mean_brier']} vs 0.25"}
    merge(la, nar.get('last_analysis', {}))
    for k, v in nar.get('rule_candidates_append', {}).items():
        la['rule_candidates'][k] += v

    rpt = {'trade_date': day, 'report_date': rep, 'A_pts': A_pts, 'LL': LL, 'SL': SL, 'grade': g, 'brier': brier, 'roll': s['rolling_direction_score_pct'],
           'base': base, 'amp': at['summary'], 'shadow': sh['summary'], 'shadow_today': shadow_res,
           'narrative_keys': sorted(nar.get('last_analysis', {}).keys()), 'wrote': bool(a.out)}
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        sv(os.path.join(a.out, 'track_record.json'), tr)
        sv(os.path.join(a.out, 'pnl_ledger.json'), pnl)
        sv(os.path.join(a.out, 'last_analysis.json'), la)
    open(a.report, 'w', encoding='utf-8').write(json.dumps(rpt, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--docs', required=True)
    ap.add_argument('--today', required=True)
    ap.add_argument('--narrative')
    ap.add_argument('--report-date')
    ap.add_argument('--out')
    ap.add_argument('--report', default='mech_report.txt')
    run(ap.parse_args())
