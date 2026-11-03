"""SPX 每日 HTML 報告：數字、表格、固定段落由已更新的三本帳產生，敘事由 narrative JSON 的 html 區塊提供（可含 <b>）。

  python scripts/render_spx_html.py --docs <已更新帳本的資料夾> --today scripts/today_data.txt --narrative narrative_MMDD.json \\
      --head-from docs/spx-analysis-<前一份>.html --out docs/spx-analysis-YYYYMMDD.html

版型（<head> 的 CSS）沿用 --head-from 那份報告，只換 <title> 的日期。
"""
import argparse
import html
import os
import re

from mech_lib import hu, ld, md

FILES = ('track_record.json', 'pnl_ledger.json', 'last_analysis.json')
FILL = {0.2: ('65%', '32%', '72%', '41%'), 0.4: ('51%', '21%', '58%', '26%'), 0.6: ('39%', '16%', '43%', '16%'), 0.8: ('30%', '11%', '32%', '9%')}
DIRW = {'up': '漲', 'down': '跌', 'flat': '平'}
CLS = {'up': 'up', 'down': 'dn', 'flat': 'nu'}
REQUIRED = ('backtest_notes', 'deviation', 'amp_note', 'macro_title', 'macro_note', 'regime_labels', 'regime_warn', 'breadth_note',
            'price_rows', 'granville', 'chan_note', 'elliott_rows', 'bias_note', 'levels', 'notes_catalyst', 'notes_watch')
BOLD = re.compile(r'[*][*](.+?)[*][*]')


def kpi(lb, vl, cls, nt):
    return f'  <div class="kpi"><div class="lb">{lb}</div><div class="vl {cls}">{vl}</div><div class="nt">{nt}</div></div>'


def grid(items):
    return '<div class="grid g4">\n' + '\n'.join(items) + '\n</div>'


def table(head, rows):
    return '<div class="scroll"><table>\n<tr>' + ''.join(f'<th>{x}</th>' for x in head) + '</tr>\n' + '\n'.join(rows) + '\n</table></div>'


def row4(r):
    return f'<tr><td>{r[0]}</td><td class="num">{r[1]}</td><td{f" class={chr(34)}{r[2]}{chr(34)}" if r[2] else ""}>{r[3]}</td></tr>'


def head_from(path, date):
    with open(path, encoding='utf-8') as f:
        head = f.read().split('<body>', 1)[0]
    return re.sub(r'(<title>[^<]*?)\d{4}-\d{2}-\d{2}', lambda m: m.group(1) + date, head, count=1)


def render(ledgers, td, nar, head):
    tr, pl, la = (ledgers[f] for f in FILES)
    H = nar['html']
    miss = [k for k in REQUIRED if not H.get(k)]
    if miss:
        raise SystemExit('narrative.html 缺必填欄位：' + '、'.join(miss))
    rep, day = la['trade_date'], td['trade_date']
    C, chg = td['close'], td['change_pct']
    am, pr = la['amplitude'], la['predictions']
    A, Ap = am['A_pct'], am['A_pts']
    ae, at = tr['amp_track']['entries'][-1], tr['amp_track']['summary']
    t = ae['eval_date']
    prev = [x for x in tr['entries'] if x.get('actual_date') == t][-1]
    ev = [x for x in pl['entries'] if x.get('eval_date') == t][-1]['ohlc']
    s, b = tr['summary'], tr['summary']['brier']
    ps, sh = pl['summary'], pl['shadow_ledger']
    shd = {x['side']: x for x in sh['entries'] if x['eval_date'] == t}
    bp = la['backtest_prev']
    base = bp['always_neutral_baseline_pct']
    d = prev['actual_dir']
    K = H.get('ledger_kpi_notes', {})
    out = [f'<header>\n  <h1>S&amp;P 500 <span>日線分析</span> — {rep}</h1>\n'
           f'  <div class="sub">資料基準：{day} 美股收盤　｜　{C:,.2f}（{chg:+.2f}%）　｜　隔日振幅 A {hu(A, 2):.2f}%（±{round(Ap)} 點）・方向 50 無 edge・不掛實單　｜　SPX 系統・Phase 3</div>\n</header>',
           f'<h2>第一區 · 回測驗證（{md(t)} 預測 vs 實際）</h2>',
           grid([kpi('上次預測', '50', 'nu', '中性・方向無 edge・不掛實單'),
                 kpi(f'{md(t)} 收盤', f"{prev['actual_pct']:+.2f}%", CLS[d], f"{ev['c']:,.2f}（{d}）"),
                 kpi('方向判定', prev['grade'].upper(), 'nu', f"中性遇{DIRW[d]}｜Brier {bp['brier'] if bp['brier'] is not None else '排除'}"),
                 kpi('當日 P&amp;L', '0bp', 'nu', f"預設不掛｜累積 <b>{ps['cumulative_weighted_bp']}</b>")])]
    out += [f'<div class="note">\n{x}\n</div>' for x in H['backtest_notes']]
    out.append(f"<h3>Phase 3 帳本：第 {at['graded']} 筆判定</h3>")

    def sh_kpi(side):
        x = shd[side]
        lab = f"影子{'多' if side == 'long' else '空'} {x['limit']:,.2f}"
        if not x['filled']:
            return kpi(lab, '未成交', 'nu', K.get(side, f"{'低' if side == 'long' else '高'} {ev['l'] if side == 'long' else ev['h']:,.2f}"))
        return kpi(lab, f"{x['pnl_A']:+.3f}A", 'up' if x['pnl_A'] > 0 else 'dn', K.get(side, f"成交 {x['fill']:,.2f}；停損 {x['stop']:,.2f}"))
    out.append(grid([kpi('振幅帳 amp_track', f"{hu(ae['actual_range_pct'], 2):.2f}%", 'up' if ae['in_band'] else 'dn',
                         K.get('amp', f"預報 A {hu(ae['A_pct'], 2):.2f}%（區間 {hu(ae['band_lo'], 2):.2f}–{hu(ae['band_hi'], 2):.2f}%）→ <b>{'區間內' if ae['in_band'] else '區間外'}</b>")),
                     kpi('log_err vs r0', f"{ae['log_err']:.3f}", 'up' if ae['log_err'] < ae['r0_log_err'] else 'dn', K.get('logerr', f"舊算法 r0 {ae['r0_log_err']:.3f}")),
                     sh_kpi('long'), sh_kpi('short')]))
    out.append(f'<div class="warn">\n{H["deviation"]}\n</div>')
    ss = sh['summary']
    out.append(grid([kpi('方向分數', f"{s['rolling_direction_score_pct']}%", 'cy', f"{s['graded']} 筆｜<b>每天報中性 {base}%</b>"),
                     kpi('mean Brier', f"{b['mean_brier']}", 'nu', f"基準 0.25（{b['included']} 筆，flat {b['excluded_flat']} 筆排除）"),
                     kpi('P&amp;L 累積', f"{ps['cumulative_weighted_bp']}bp", 'dn' if ps['cumulative_weighted_bp'] < 0 else 'up', f"{ps['days_evaluated']} 日｜Phase 3 主帳休眠"),
                     kpi('影子帳累積', f"{ss['cum_pnl_A']}A", 'dn' if ss['cum_pnl_A'] < 0 else 'up',
                         f"{ss['evaluated_days']} 日｜多 {ss['filled_long']} 筆平均 {ss['mean_pnl_A_long']}A、空 {ss['filled_short']} 筆平均 {ss['mean_pnl_A_short']}A")]))
    r17 = f"依 rule17 並列：系統 {s['rolling_direction_score_pct']}% vs 每天報中性 {base}%；Brier {b['mean_brier']} vs 0.25。"
    out.append(f'<div class="note">{H.get("rule17_note", r17)}</div>')

    out.append(f'<h2>第二區 · 今日分析（{md(day)} 收盤）</h2>')
    vp = am['vol_pct_1y']
    env = '平靜（<33%）' if vp < 33 else '一般環境（33–67%）' if vp <= 67 else '波動偏高（>67%）'
    out.append('<div class="big">\n' + grid([kpi('隔日振幅預報 A', f'{hu(A, 2):.2f}%', 'cy', f'約 ±{round(Ap)} 點（{Ap}）'),
                                             kpi('50% 區間', f"{hu(am['band_lo'], 2):.2f}–{hu(am['band_hi'], 2):.2f}%", 'cy', f"c {am['c']}｜近 63 日實際÷隱含 {am['realized_vs_implied_63d']:.2f}"),
                                             kpi('方向（拉回機率）', '50', 'nu', '中性・方向無 edge（rule63）'),
                                             kpi('VIX 一年分位', f'{vp}%', 'nu', env)]).replace('<div class="grid g4">', '  <div class="grid g4">', 1)
               + f"\n  <div class=\"note\" style=\"margin-bottom:0\">隔日振幅預報：A = {hu(A, 2):.2f}%（約 ±{round(Ap)} 點）｜50% 區間 {hu(am['band_lo'], 2):.2f}–{hu(am['band_hi'], 2):.2f}%｜"
                 f"c = {am['c']}（近 63 日實際÷隱含 {am['realized_vs_implied_63d']:.2f}）。{H['amp_note']}舊算法 r0 參考 {hu(am['r0_ref_pct'], 2):.2f}%。</div>\n</div>")
    m = la.get('macro_layer', {})
    out.append(f"<h3>盤前宏觀層（{H['macro_title']}）</h3>")
    if all(k in m for k in ('es_pct', 'es_pt_chg_since_spx_close', 'implied_spx_open', 'nq_pct', 'us10y_pct')):
        out.append(grid([kpi('ES 期貨', f"{m['es_pct']:+.2f}%", 'up' if m['es_pct'] > 0 else 'dn', f"對前日結算；自 SPX 收盤 {m['es_pt_chg_since_spx_close']} 點"),
                         kpi('隱含開盤', f"≈{m['implied_spx_open']:,.0f}", 'nu', f"{m['es_pt_chg_since_spx_close'] / Ap:.2f}A"),
                         kpi('NQ／SOXX', f"{m['nq_pct']:+.2f}%", 'up' if m['nq_pct'] > 0 else 'dn', H.get('nq_note', '')),
                         kpi('10Y／DXY', f"{m['us10y_pct']}%", 'nu', H.get('rates_note', f"DXY {m.get('dxy', '')}"))]))
    out.append(f'<div class="note">{H["macro_note"]}</div>')
    rg, h1 = td['regime'], td['regime']['horizon_1d']
    out.append('<h3>環境水位（regime）</h3>')
    out.append(f"<pre>環境水位（regime）：1D 拉回 {h1['regime_avg_1d']}%（基準 {h1['base_1d_pullback']}%，{h1['regime_avg_vs_base']:+.1f}pp）｜"
               f"5D 拉回 {rg['regime_avg_5d']}%（基準 {rg['base_5d_pullback']}%，{rg['regime_avg_vs_base']:+.1f}pp）\n"
               + '\n'.join(f"  {'└' if i == 2 else '├'} {lab}：{H['regime_labels'][i]} → 1D {h1[k]['pullback_1d']:.1f}% ／ 5D {rg[k]['pullback_5d']:.1f}%"
                           for i, (lab, k) in enumerate((('VIX', 'vix'), ('趨勢', 'trend'), ('MA20', 'ma20_ext'))))
               + '\n（拉回定義：盤中低點跌破訊號日收盤 −0.75%；1D＝隔日、5D＝未來 5 日）</pre>')
    out.append(f'<div class="warn">{H["regime_warn"]}</div>')
    out += ['<h3>0. 廣度</h3>', f'<div class="note">{H["breadth_note"]}</div>',
            '<h3>1–3. 價格行為・均線・指標</h3>', table(['項目', '數值', '讀法'], [row4(r) for r in H['price_rows']]),
            '<h3>4. 葛蘭威爾八大法則</h3>', '<div class="gr">\n' + '\n'.join(f'  <div class="gc"><div class="h">{g[0]}</div>{g[1]}</div>' for g in H['granville']) + '\n</div>',
            '<h3>5–6. 纏論＋艾略特波浪（敘事，不推導 headline）</h3>', f'<div class="note">{H["chan_note"]}</div>',
            table(['方案', '敘事權重', '路徑'], [row4(r) for r in H['elliott_rows']]), f'<div class="note">{H["bias_note"]}</div>',
            '<h3>關鍵位</h3>', table(['壓力', '來源', '支撐', '來源'], [f'<tr><td class="num dn">{r[0]}</td><td>{r[1]}</td><td class="num up">{r[2]}</td><td>{r[3]}</td></tr>' for r in H['levels']])]

    out.append(f'<h2>第三區 · 明日掛單（{md(rep)}）</h2>')
    out.append('<div class="big"><b class="nu">本日無已核准的方向 edge → 不掛實單（rule65）。</b>2014–2026 不帶方向的限價單 30 種組合全部負期望；沒有方向 edge 時，掛單本身就是負期望。</div>')
    out.append(f'<h3>若要掛單：各距離與事前成交率（A＝{Ap} 點，自收盤 {C:,.2f}）</h3>')
    out.append(table(['k', '多單掛價', '多單成交率（跳空成交）', '空單掛價', '空單成交率（跳空成交）'],
                     [f'<tr><td class="num">{r["k"]}</td><td class="num">{C - r["k"] * Ap:,.0f}</td><td class="num">{FILL[r["k"]][0]}（{FILL[r["k"]][1]}）</td>'
                      f'<td class="num">{C + r["k"] * Ap:,.0f}</td><td class="num">{FILL[r["k"]][2]}（{FILL[r["k"]][3]}）</td></tr>' for r in pr['geometry_A']['rows']]))
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
        f'<tr><td>22:00 開盤確認</td><td>首 30 分 K 振幅 ÷ A</td><td>≥ 0.7A（≈ {round(0.7 * Ap)} 點）＝當日振幅很可能超過區間上緣 {hu(am["band_hi"], 2):.2f}%</td></tr>',
        '<tr><td>22:30 睡前檢查</td><td>關鍵位守住／跌破＋已用掉幾個 A</td><td>部位建議只在對話輸出（rule19／rule32）</td></tr>']))
    out.append('<h3>監控清單</h3>')
    out.append('<ul>\n' + '\n'.join('<li>' + BOLD.sub(r'<b>\1</b>', w) + '</li>' for w in pr.get('watch_points', [])) + '\n</ul>')
    zs, ks, kr = pr['zhongshu'], pr['key_support'], pr['key_resistance']
    out.append('<h3>市場筆記速記</h3>')
    out.append(f"<pre>📋 市場筆記速記（可直接貼入 App）\n\n日期：{rep}\n收盤：{C:,.0f}（{chg:+.2f}%）\nVIX：{td['vix']}\n拉回機率：50%（方向無 edge）\n"
               f"隔日振幅：{hu(A, 2):.2f}%（50% 區間 {hu(am['band_lo'], 2):.2f}–{hu(am['band_hi'], 2):.2f}%）\n\n"
               f"纏論中樞：{zs['lower']:,.0f} – {zs['upper']:,.0f}\n關鍵支撐：{H.get('notes_support') or ' / '.join(f'{x:,}' for x in ks[:3])}\n"
               f"關鍵阻力：{H.get('notes_resistance') or ' / '.join(f'{x:,}' for x in kr[:3])}\n\n"
               f"今日催化劑：{html.escape(H['notes_catalyst'], quote=False)}\n明日觀察：{H['notes_watch']}\n\n策略摘要：\n實單：不掛（本日無已核准的方向 edge）\n"
               f"影子單：多 {pend['long']['limit']:,.0f}（停損 {pend['long']['limit'] - 0.5 * Ap:,.0f}）｜空 {pend['short']['limit']:,.0f}（停損 {pend['short']['limit'] + 0.5 * Ap:,.0f}）\n\n"
               f"📌 回測參照（下次勿刪）：\n拉回機率 50%｜支撐 {ks[0]:,} / {ks[1]:,}｜阻力 {kr[0]:,} / {kr[1]:,}｜纏論上沿 {zs['upper']:,.0f}</pre>")
    if H.get('footer_note'):
        out.append(f'<div class="note">{H["footer_note"]}</div>')
    out.append(f'<footer>本分析僅供學習參考，不構成投資建議｜SPX 系統 · Phase 3 · {rep} · <a href="https://johnnyhsu5509.github.io/spx-analysis/spx/" style="color:var(--cyan)">固定入口</a></footer>')
    return head + '<body>\n<div class="wrap">\n\n' + '\n\n'.join(out) + '\n</div>\n</body>\n</html>\n'


def main(argv=None):
    p = argparse.ArgumentParser()
    for k in ('--docs', '--today', '--narrative', '--head-from', '--out'):
        p.add_argument(k, required=True)
    a = p.parse_args(argv)
    ledgers = {f: ld(os.path.join(a.docs, f)) for f in FILES}
    page = render(ledgers, ld(a.today), ld(a.narrative), head_from(a.head_from, ledgers['last_analysis.json']['trade_date']))
    with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(page)


if __name__ == '__main__':
    main()
