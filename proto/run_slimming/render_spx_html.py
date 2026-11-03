"""SPX 每日 HTML 報告渲染器原型：數字與固定段落由帳本產生，敘事由 narrative JSON 的 html 區塊提供（純文字，可含 <b>）。

用法：python3 render_spx_html.py --docs DIR（已更新的三本帳）--today today_data.txt --narrative narrative.json --css report_head.css --out spx-analysis-YYYYMMDD.html
模型不再手寫整份 HTML；每天只寫敘事，版型、數字、表格由程式負責，數字一定跟帳本一致。
"""
import argparse, datetime, html, json, os, re

FILL = {0.2: ('65%', '32%', '72%', '41%'), 0.4: ('51%', '21%', '58%', '26%'), 0.6: ('39%', '16%', '43%', '16%'), 0.8: ('30%', '11%', '32%', '9%')}
DIRW = {'up': '漲', 'down': '跌', 'flat': '平'}
CLS = {'up': 'up', 'down': 'dn', 'flat': 'nu'}


def ld(p):
    return json.load(open(p, encoding='utf-8'))


def md(d):
    t = datetime.date.fromisoformat(d[:10])
    return f'{t.month}/{t.day}'


def kpi(lb, vl, cls, nt):
    return f'  <div class="kpi"><div class="lb">{lb}</div><div class="vl {cls}">{vl}</div><div class="nt">{nt}</div></div>'


def grid(items):
    return '<div class="grid g4">\n' + '\n'.join(items) + '\n</div>'


def table(head, rows):
    h = '<tr>' + ''.join(f'<th>{x}</th>' for x in head) + '</tr>'
    return '<div class="scroll"><table>\n' + h + '\n' + '\n'.join(rows) + '\n</table></div>'


def run(a):
    tr, pl, la = (ld(os.path.join(a.docs, f)) for f in ('track_record.json', 'pnl_ledger.json', 'last_analysis.json'))
    td, nar = ld(a.today), ld(a.narrative)
    H = nar['html']
    rep, day = la['trade_date'], td['trade_date']
    C, chg, O, Hh, Lo = td['close'], td['change_pct'], td['open'], td['high'], td['low']
    am, pr = la['amplitude'], la['predictions']
    A, Ap = am['A_pct'], am['A_pts']
    prev = [x for x in tr['entries'] if x.get('actual_date') == day][-1]
    s, b = tr['summary'], tr['summary']['brier']
    at, ae = tr['amp_track']['summary'], tr['amp_track']['entries'][-1]
    ps, sh = pl['summary'], pl['shadow_ledger']
    shd = {x['side']: x for x in sh['entries'] if x['eval_date'] == day}
    bp = la['backtest_prev']
    base = bp['always_neutral_baseline_pct']
    d = prev['actual_dir']
    out = []
    out.append(f'<header>\n  <h1>S&amp;P 500 <span>日線分析</span> — {rep}</h1>\n'
               f'  <div class="sub">資料基準：{day} 美股收盤　｜　{C:,.2f}（{chg:+.2f}%）　｜　隔日振幅 A {A:.2f}%（±{round(Ap)} 點）・方向 50 無 edge・不掛實單　｜　SPX 系統・Phase 3</div>\n</header>')
    out.append(f'<h2>第一區 · 回測驗證（{md(day)} 預測 vs 實際）</h2>')
    out.append(grid([kpi('上次預測', '50', 'nu', '中性・方向無 edge・不掛實單'),
                     kpi(f'{md(day)} 收盤', f'{chg:+.2f}%', CLS[d], f'{C:,.2f}（{d}）'),
                     kpi('方向判定', prev['grade'].upper(), 'nu', f"中性遇{DIRW[d]}｜Brier {bp['brier'] if bp['brier'] is not None else '排除'}"),
                     kpi('當日 P&amp;L', '0bp', 'nu', f"預設不掛｜累積 <b>{ps['cumulative_weighted_bp']}</b>")]))
    out += [f'<div class="note">\n{x}\n</div>' for x in H['backtest_notes']]
    out.append(f"<h3>Phase 3 帳本：第 {at['graded']} 筆判定</h3>")
    K = H.get('ledger_kpi_notes', {})

    def sh_kpi(side):
        x = shd[side]
        lab = f"影子{'多' if side == 'long' else '空'} {x['limit']:,.2f}"
        if not x['filled']:
            return kpi(lab, '未成交', 'nu', K.get(side, f"{'低' if side == 'long' else '高'} {Lo if side == 'long' else Hh:,.2f}"))
        return kpi(lab, f"{x['pnl_A']:+.3f}A", 'up' if x['pnl_A'] > 0 else 'dn', K.get(side, f"成交 {x['fill']:,.2f}；停損 {x['stop']:,.2f}"))
    out.append(grid([kpi('振幅帳 amp_track', f"{ae['actual_range_pct']:.2f}%", 'up' if ae['in_band'] else 'dn',
                         K.get('amp', f"預報 A {ae['A_pct']:.2f}%（區間 {ae['band_lo']:.2f}–{ae['band_hi']:.2f}%）→ <b>{'區間內' if ae['in_band'] else '區間外'}</b>")),
                     kpi('log_err vs r0', f"{ae['log_err']:.3f}", 'up' if ae['log_err'] < ae['r0_log_err'] else 'dn', K.get('logerr', f"舊算法 r0 {ae['r0_log_err']:.3f}")),
                     sh_kpi('long'), sh_kpi('short')]))
    out.append(f'<div class="warn">\n{H["deviation"]}\n</div>')
    fl = [x for x in sh['entries'] if x['side'] == 'long' and x['filled']]
    fs = [x for x in sh['entries'] if x['side'] == 'short' and x['filled']]
    out.append(grid([kpi('方向分數', f"{s['rolling_direction_score_pct']}%", 'cy', f"{s['graded']} 筆｜<b>每天報中性 {base}%</b>"),
                     kpi('mean Brier', f"{b['mean_brier']}", 'nu', f"基準 0.25（{b['included']} 筆，flat {b['excluded_flat']} 筆排除）"),
                     kpi('P&amp;L 累積', f"{ps['cumulative_weighted_bp']}bp", 'dn' if ps['cumulative_weighted_bp'] < 0 else 'up', f"{ps['days_evaluated']} 日｜Phase 3 主帳休眠"),
                     kpi('影子帳累積', f"{sh['summary']['cum_pnl_A']}A", 'dn' if sh['summary']['cum_pnl_A'] < 0 else 'up',
                         f"{sh['summary']['evaluated_days']} 日｜多 {len(fl)} 筆 {sh['summary']['mean_pnl_A_long']}A、空 {len(fs)} 筆平均 {sh['summary']['mean_pnl_A_short']}A")]))
    r17 = f"依 rule17 並列：系統 {s['rolling_direction_score_pct']}% vs 每天報中性 {base}%；Brier {b['mean_brier']} vs 0.25。"
    out.append(f'<div class="note">{H.get("rule17_note", r17)}</div>')

    out.append(f'<h2>第二區 · 今日分析（{md(day)} 收盤）</h2>')
    vp = am['vol_pct_1y']
    env = '平靜（<33%）' if vp < 33 else '一般環境（33–67%）' if vp <= 67 else '波動偏高（>67%）'
    out.append('<div class="big">\n' + grid([kpi('隔日振幅預報 A', f'{A:.2f}%', 'cy', f'約 ±{round(Ap)} 點（{Ap}）'),
                                             kpi('50% 區間', f"{am['band_lo']:.2f}–{am['band_hi']:.2f}%", 'cy', f"c {am['c']}｜近 63 日實際÷隱含 {am['realized_vs_implied_63d']:.2f}"),
                                             kpi('方向（拉回機率）', '50', 'nu', '中性・方向無 edge（rule63）'),
                                             kpi('VIX 一年分位', f'{vp}%', 'nu', env)]).replace('<div class="grid g4">', '  <div class="grid g4">', 1)
               + f"\n  <div class=\"note\" style=\"margin-bottom:0\">隔日振幅預報：A = {A:.2f}%（約 ±{round(Ap)} 點）｜50% 區間 {am['band_lo']:.2f}–{am['band_hi']:.2f}%｜c = {am['c']}（近 63 日實際÷隱含 {am['realized_vs_implied_63d']:.2f}）。{H['amp_note']}舊算法 r0 參考 {am['r0_ref_pct']:.2f}%。</div>\n</div>")
    m = la['macro_layer']
    out.append(f"<h3>盤前宏觀層（{H['macro_title']}）</h3>")
    out.append(grid([kpi('ES 期貨', f"{m['es_pct']:+.2f}%", 'up' if m['es_pct'] > 0 else 'dn', f"對前日結算；自 SPX 收盤 {m['es_pt_chg_since_spx_close']} 點"),
                     kpi('隱含開盤', f"≈{m['implied_spx_open']:,.0f}", 'nu', f"{m['es_pt_chg_since_spx_close'] / Ap:.2f}A"),
                     kpi('NQ／SOXX', f"{m['nq_pct']:+.2f}%", 'up' if m['nq_pct'] > 0 else 'dn', H.get('nq_note', '')),
                     kpi('10Y／DXY', f"{m['us10y_pct']}%", 'nu', H.get('rates_note', f"DXY {m['dxy']}"))]))
    out.append(f'<div class="note">{H["macro_note"]}</div>')
    rg, h1 = td['regime'], td['regime']['horizon_1d']
    out.append('<h3>環境水位（regime）</h3>')
    out.append(f"<pre>環境水位（regime）：1D 拉回 {h1['regime_avg_1d']}%（基準 {h1['base_1d_pullback']}%，{h1['regime_avg_vs_base']:+.1f}pp）｜5D 拉回 {rg['regime_avg_5d']}%（基準 {rg['base_5d_pullback']}%，{rg['regime_avg_vs_base']:+.1f}pp）\n"
               + '\n'.join(f"  {'└' if i == 2 else '├'} {lab}：{H['regime_labels'][i]} → 1D {h1[k]['pullback_1d']:.1f}% ／ 5D {rg[k]['pullback_5d']:.1f}%"
                           for i, (lab, k) in enumerate((('VIX', 'vix'), ('趨勢', 'trend'), ('MA20', 'ma20_ext'))))
               + '\n（拉回定義：盤中低點跌破訊號日收盤 −0.75%；1D＝隔日、5D＝未來 5 日）</pre>')
    out.append(f'<div class="warn">{H["regime_warn"]}</div>')
    out.append('<h3>0. 廣度</h3>')
    out.append(f'<div class="note">{H["breadth_note"]}</div>')
    out.append('<h3>1–3. 價格行為・均線・指標</h3>')
    out.append(table(['項目', '數值', '讀法'], [f'<tr><td>{r[0]}</td><td class="num">{r[1]}</td><td{(" class=" + chr(34) + r[2] + chr(34)) if r[2] else ""}>{r[3]}</td></tr>' for r in H['price_rows']]))
    out.append('<h3>4. 葛蘭威爾八大法則</h3>')
    out.append('<div class="gr">\n' + '\n'.join(f'  <div class="gc"><div class="h">{g[0]}</div>{g[1]}</div>' for g in H['granville']) + '\n</div>')
    out.append('<h3>5–6. 纏論＋艾略特波浪（敘事，不推導 headline）</h3>')
    out.append(f'<div class="note">{H["chan_note"]}</div>')
    out.append(table(['方案', '敘事權重', '路徑'], [f'<tr><td>{r[0]}</td><td class="num">{r[1]}</td><td{(" class=" + chr(34) + r[2] + chr(34)) if r[2] else ""}>{r[3]}</td></tr>' for r in H['elliott_rows']]))
    out.append(f'<div class="note">{H["bias_note"]}</div>')
    out.append('<h3>關鍵位</h3>')
    out.append(table(['壓力', '來源', '支撐', '來源'], [f'<tr><td class="num dn">{r[0]}</td><td>{r[1]}</td><td class="num up">{r[2]}</td><td>{r[3]}</td></tr>' for r in H['levels']]))

    out.append(f'<h2>第三區 · 明日掛單（{md(rep)}）</h2>')
    out.append('<div class="big"><b class="nu">本日無已核准的方向 edge → 不掛實單（rule65）。</b>2014–2026 不帶方向的限價單 30 種組合全部負期望；沒有方向 edge 時，掛單本身就是負期望。</div>')
    out.append(f'<h3>若要掛單：各距離與事前成交率（A＝{Ap} 點，自收盤 {C:,.2f}）</h3>')
    out.append(table(['k', '多單掛價', '多單成交率（跳空成交）', '空單掛價', '空單成交率（跳空成交）'],
                     [f'<tr><td class="num">{r["k"]}</td><td class="num">{C - r["k"] * Ap:,.0f}</td><td class="num">{FILL[r["k"]][0]}（{FILL[r["k"]][1]}）</td><td class="num">{C + r["k"] * Ap:,.0f}</td><td class="num">{FILL[r["k"]][2]}（{FILL[r["k"]][3]}）</td></tr>' for r in pr['geometry_A']['rows']]))
    if H.get('fill_note'):
        out.append(f'<div class="note">{H["fill_note"]}</div>')
    pend = {x['side']: x for x in sh['pending']}
    out.append('<h3>影子單（只記 shadow_ledger，不進 P&amp;L 主帳）</h3>')
    out.append(table(['方向', '掛單', '停損', '出場'], [
        f"<tr><td class=\"up\">影子多</td><td class=\"num\">limit_buy {pend['long']['limit']:,.2f}（收盤 −{pend['long']['k']}A）</td><td class=\"num\">成交價 −0.5A（以掛價成交則 {pend['long']['limit'] - 0.5 * Ap:,.2f}）</td><td>隔日收盤</td></tr>",
        f"<tr><td class=\"dn\">影子空</td><td class=\"num\">limit_sell {pend['short']['limit']:,.2f}（收盤 +{pend['short']['k']}A）</td><td class=\"num\">成交價 +0.5A（以掛價成交則 {pend['short']['limit'] + 0.5 * Ap:,.2f}）</td><td>隔日收盤</td></tr>"]))
    out.append('<h3>三層振幅檢查</h3>')
    out.append(table(['時點（台北）', '檢查', '門檻'], [
        f'<tr><td>白天（本報告）</td><td>VIX 一年分位 {vp}%</td><td>{env.split("（")[0]}</td></tr>',
        f'<tr><td>21:20 期貨確認</td><td>ES 隱含開盤距前收 ÷ A</td><td>|距離| ≥ 1.0A（≈ ±{round(Ap)} 點，{C - Ap:,.0f}／{C + Ap:,.0f}）＝開盤已用掉一整天的預期振幅</td></tr>',
        f'<tr><td>22:00 開盤確認</td><td>首 30 分 K 振幅 ÷ A</td><td>≥ 0.7A（≈ {round(0.7 * Ap)} 點）＝當日振幅很可能超過區間上緣 {am["band_hi"]:.2f}%</td></tr>',
        '<tr><td>22:30 睡前檢查</td><td>關鍵位守住／跌破＋已用掉幾個 A</td><td>部位建議只在對話輸出（rule19／rule32）</td></tr>']))
    out.append('<h3>監控清單</h3>')
    bold = re.compile(r'[*][*](.+?)[*][*]')
    out.append('<ul>\n' + '\n'.join('<li>' + bold.sub(r'<b>\1</b>', w) + '</li>' for w in pr['watch_points']) + '\n</ul>')
    zs = pr['zhongshu']
    ks, kr = pr['key_support'], pr['key_resistance']
    out.append('<h3>市場筆記速記</h3>')
    out.append(f"<pre>📋 市場筆記速記（可直接貼入 App）\n\n日期：{rep}\n收盤：{C:,.0f}（{chg:+.2f}%）\nVIX：{td['vix']}\n拉回機率：50%（方向無 edge）\n隔日振幅：{A:.2f}%（50% 區間 {am['band_lo']:.2f}–{am['band_hi']:.2f}%）\n\n"
               f"纏論中樞：{zs['lower']:,.0f} – {zs['upper']:,.0f}\n關鍵支撐：{H.get('notes_support') or ' / '.join(f'{x:,}' for x in ks[:3])}\n關鍵阻力：{H.get('notes_resistance') or ' / '.join(f'{x:,}' for x in kr[:3])}\n\n"
               f"今日催化劑：{html.escape(H['notes_catalyst'], quote=False)}\n明日觀察：{H['notes_watch']}\n\n策略摘要：\n實單：不掛（本日無已核准的方向 edge）\n"
               f"影子單：多 {pend['long']['limit']:,.0f}（停損 {pend['long']['limit'] - 0.5 * Ap:,.0f}）｜空 {pend['short']['limit']:,.0f}（停損 {pend['short']['limit'] + 0.5 * Ap:,.0f}）\n\n"
               f"📌 回測參照（下次勿刪）：\n拉回機率 50%｜支撐 {ks[0]:,} / {ks[1]:,}｜阻力 {kr[0]:,} / {kr[1]:,}｜纏論上沿 {zs['upper']:,.0f}</pre>")
    if H.get('footer_note'):
        out.append(f'<div class="note">{H["footer_note"]}</div>')
    out.append(f'<footer>本分析僅供學習參考，不構成投資建議｜SPX 系統 · Phase 3 · {rep} · <a href="https://johnnyhsu5509.github.io/spx-analysis/spx/" style="color:var(--cyan)">固定入口</a></footer>')
    head = open(a.css, encoding='utf-8').read().replace('__DATE__', rep)
    page = head + '<body>\n<div class="wrap">\n\n' + '\n\n'.join(out) + '\n</div>\n</body>\n</html>\n'
    open(a.out, 'w', encoding='utf-8', newline='\n').write(page)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for k in ('--docs', '--today', '--narrative', '--css', '--out'):
        p.add_argument(k, required=True)
    run(p.parse_args())
