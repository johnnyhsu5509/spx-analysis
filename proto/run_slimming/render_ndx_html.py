"""NDX 每日 HTML 報告渲染器原型（對應每日手寫的 _ndx_MMDD_body.html）。數字由帳本與 ndx_last_analysis 產生，敘事由 narrative JSON 的 html 區塊提供。"""
import argparse, datetime, json, os, re
from decimal import Decimal, ROUND_HALF_UP

FILL = {0.2: ('65%（43% 跳空）', '73%（53% 跳空）'), 0.4: ('51%（34%）', '58%（41%）'), 0.6: ('39%（28%）', '44%（29%）'), 0.8: ('30%（24%）', '32%（20%）')}
BOLD = re.compile(r'[*][*](.+?)[*][*]')


def ld(p):
    return json.load(open(p, encoding='utf-8'))


def md(d):
    t = datetime.date.fromisoformat(d[:10])
    return f'{t.month}/{t.day}'


def hu(x, nd=1):
    return float(Decimal(str(x)).quantize(Decimal(1).scaleb(-nd), ROUND_HALF_UP))


def sg(x, nd=3, unit=''):
    return (f'{hu(x, nd):+.{nd}f}' + unit).replace('-', '−')


def k(l, v, vc, n, nc=''):
    return f'  <div class="k"><div class="l">{l}</div><div class="v {vc}">{v}</div><div class="n{(" " + nc) if nc else ""}">{n}</div></div>'


def tr(cells, cls_last=''):
    tds = ''.join(f'<td>{c}</td>' for c in cells[:-1]) + (f'<td class="{cls_last}">{cells[-1]}</td>' if cls_last else f'<td>{cells[-1]}</td>')
    return f'<tr>{tds}</tr>'


def run(a):
    la, trk, pl, td, nar = ld(a.last), ld(a.track), ld(a.pnl), ld(a.today), ld(a.narrative)
    H = nar['html']
    rep, day = la['trade_date'], td['trade_date']
    C, Hh, Lo, pc = td['close'], td['high'], td['low'], td['prev_close']
    am, pr, pos = la['amplitude'], la['predictions'], la['position_level']
    A, Ap = am['A_pct'], am['A_pts']
    prev = [x for x in trk['entries'] if x.get('actual_date') == day][-1]
    s, b = trk['summary'], trk['summary']['brier']
    ae, asum = trk['amp_track']['entries'][-1], trk['amp_track']['summary']
    sl = pl['shadow_ledger']
    sh = {x['side']: x for x in sl['entries'] if x['eval_date'] == day}
    ps = pl['summary']
    brier = [x for x in b['per_entry'] if x['report_date'] == prev['report_date']][-1]['brier']
    o = []
    o.append(f'<header>\n  <span class="badge">NASDAQ-100 · NDX</span>\n  <h1>{H["title"]}</h1>\n'
             f'  <div class="sub">報告日 {rep}（台北）｜資料基準 {day} 美股收盤｜Phase 3：主輸出＝隔日振幅預報，方向恆 50</div>\n</header>')
    br = la['breadth']['chg_1d_pct']
    o.append('<div class="kpi">\n' + '\n'.join([
        k('隔日振幅預報 A', f'{A:.2f}%', 'nu', f"約 ±{round(Ap)} 點｜50% 區間 {am['band_lo']:.2f}–{am['band_hi']:.2f}%"),
        k('拉回機率', '50%', 'nu', '方向無 edge（rule55）'),
        k('NDX 收盤', f'{C:,.2f}', 'nu', f"{td['change_pct']:+.2f}%｜低 {Lo:,.0f}／高 {Hh:,.0f}", 'up' if td['change_pct'] > 0 else 'dn'),
        k('QQQE / QQQ', f'{br:+.2f}%', 'up' if br > 0 else 'dn', H['breadth_kpi']),
        k('VXN', f"{td['vxn']}", 'nu', H['vxn_kpi']),
        k('部位水位', pos['state'], 'up' if pos['state'] == '正常' else 'dn', f"收盤在 MA200 {'上' if pos['pct'] > 0 else '下'} {abs(pos['pct']):.1f}%")]) + '\n</div>')
    o.append(f'<div class="box warn">\n  <h4>資料註記</h4>\n  {H["data_note"]}\n</div>')
    o.append(f'<h2>一、回測 {md(day)}（Phase 3 第 {asum["graded"]} 天）</h2>')
    rows = ['<tr><th>項目</th><th>預測</th><th>實際</th><th>結果</th></tr>',
            tr(['方向', '中性 50 → 無 edge', f"{C:,.2f}，<b>{prev['actual_pct']:+.2f}%</b> → {prev['actual_dir']}",
                f"{'✅' if prev['grade'] == 'hit' else '🟡'} {prev['grade']}｜Brier {brier if brier is not None else '排除'}"], 'nu'),
            tr(['振幅（amp_track）', f"A {ae['A_pct']}%｜區間 {ae['band_lo']}–{ae['band_hi']}%", f"(高−低)/前收 = <b>{ae['actual_range_pct']:.3f}%</b>（{Hh - Lo:.0f} 點）",
                f"{'✅ 區間內' if ae['in_band'] else '❌ 區間外'}｜log_err {ae['log_err']:.3f} vs r0 {ae['r0_log_err']:.3f}"], 'up' if ae['in_band'] else 'dn')]
    for side, lab, od, sgn in (('long', '影子多（shadow）', 'limit_buy', '−'), ('short', '影子空（shadow）', 'limit_sell', '+')):
        x = sh[side]
        act = H.get(f'shadow_actual_{side}') or (f"全日{'低' if side == 'long' else '高'} {(Lo if side == 'long' else Hh):,.2f}，未觸掛單" if not x['filled'] else f"成交 {x['fill']:,.2f} → 出場 {x['exit']:,.2f}")
        res = '未成交' if not x['filled'] else f"{sg(x['pnl_A'], 3, 'A')}（{sg(x['pnl_pts'], 1, ' 點')}）"
        rows.append(tr([lab, f"{od} {x['limit']:,.2f}｜停損 {sgn}0.5A", act, res], 'nu' if not x['filled'] else ('up' if x['pnl_A'] > 0 else 'dn')))
    rows += [tr(r[:4], r[4]) for r in H['check_rows']]
    rows.append(tr(['策略（主帳）', '預設休眠，不掛實單', '無單', '0 bp'], 'nu'))
    o.append('<div class="tw"><table>\n' + '\n'.join(rows) + '\n</table></div>')
    o.append(f'<div class="box warn">\n  {H["deviation"]}\n</div>')
    ents = sl['entries']
    fl, fs = [x for x in ents if x['side'] == 'long' and x['filled']], [x for x in ents if x['side'] == 'short' and x['filled']]
    nl, ns = sum(x['side'] == 'long' for x in ents), sum(x['side'] == 'short' for x in ents)
    ss = sl['summary']
    o.append('<div class="tw"><table>\n<tr><th>累積</th><th>數值</th><th>說明</th></tr>\n' + '\n'.join([
        f"<tr><td>P&amp;L 主帳</td><td class=\"{'dn' if ps['cumulative_weighted_bp'] < 0 else 'up'}\">{ps['cumulative_weighted_bp']} bp</td><td>當日 0bp；已結算 {ps['trades_filled']} 筆 {ps['filled_win']} 勝 {ps['filled_loss']} 敗；預設休眠</td></tr>",
        f"<tr><td>方向分數</td><td>{s['rolling_direction_score_pct']}%</td><td>n={s['graded']}；always-neutral 基準 {s['always_neutral_baseline_pct']}%（並列）</td></tr>",
        f"<tr><td>Brier</td><td>{b['mean_brier']:.4f}</td><td>n={b['included']}（平盤排除）；基準 0.25</td></tr>",
        f"<tr><td>振幅帳</td><td>n={asum['graded']}</td><td>平均 log_err {asum['mean_log_err']:.3f}（r0 {asum['mean_r0_log_err']:.3f}）｜覆蓋 {asum['band_coverage_pct']}%（目標 45–55%）｜區間上方 {asum['above_band']}、下方 {asum['below_band']}</td></tr>",
        f"<tr><td>影子帳</td><td>n={ss['days']} 天</td><td>多：成交 {len(fl)}／{nl}，平均 {sg(ss['mean_pnl_A_long'], 3, 'A')}｜空：成交 {len(fs)}／{ns}，平均 {sg(ss['mean_pnl_A_short'], 3, 'A')}｜漂移基準平均 {sg(ss['drift_bench_mean_A'], 3, 'A')}</td></tr>"]) + '\n</table></div>')
    o.append('<h2>二、七維分析（敘事與價位，不換算機率）</h2>')
    o.append('<div class="tw"><table>\n<tr><th>維度</th><th>讀數</th><th>判讀</th></tr>\n' + '\n'.join(tr(r) for r in H['dims']) + '\n</table></div>')
    el = pr['elliott']
    o.append(f"<div class=\"mono\">波浪多情景（敘事，不推導 headline）：\n主{el['main']}\n替{el['alt']}\n替{el['alt2']}</div>")
    vs = la['volatility_scale']
    o.append('<h2>三、波動尺度與主輸出</h2>')
    o.append(f"<div class=\"mono\">隔日振幅預報：A = {A:.2f}%（約 ±{round(Ap)} 點）｜50% 區間 {am['band_lo']:.2f}–{am['band_hi']:.2f}%｜c = {am['c']:.2f}（近 63 日實際÷隱含 {am['realized_vs_implied_63d']:.2f}）\n"
             f"方向：50（方向無 edge，bias 中性）\nATR14 {vs['atr14_pct']:.2f}%｜近 5 日均振幅 {vs['range5_pct']:.2f}%｜A_NDX ÷ A_SPX = {A:.2f} ÷ {vs['spx_A_pct']:.2f} = {vs['A_ratio_ndx_spx']:.2f}</div>")
    o.append(f'<div class="box warn">\n  {H["amp_warn"]}\n</div>')
    rc, cc = la['regime_check'], la['spx_cross_check']
    h1, h5 = rc['h1d'], rc['h5d']
    lab = H['regime_labels']
    o.append('<h2>四、環境水位（regime）與 SPX 對照</h2>')
    o.append(f"<div class=\"mono\">環境水位（regime）：1D 拉回 {hu(h1['avg']):.1f}%（基準 {hu(h1['base']):.1f}%，{hu(h1['vs_base']):+.1f}pp）｜5D 拉回 {hu(h5['avg']):.1f}%（基準 {hu(h5['base']):.1f}%，{hu(h5['vs_base']):+.1f}pp）\n"
             f"  ├ VXN：{lab[0]}→ 1D {hu(h1['vxn']):.1f}% ／ 5D {hu(h5['vxn']):.1f}%\n  ├ 趨勢：{lab[1]}→ 1D {hu(h1['trend']):.1f}% ／ 5D {hu(h5['trend']):.1f}%\n  └ MA20：{lab[2]}→ 1D {hu(h1['ma20']):.1f}% ／ 5D {hu(h5['ma20']):.1f}%\n"
             f"（拉回定義：盤中低點跌破訊號日收盤 −1.00%；只作環境水位，不產生倉位指令）\n\n"
             f"NDX：振幅 A {cc['ndx']['A_pct']:.2f}%｜regime 1D 超額 {cc['ndx']['regime_1d_vs_base']:+.1f}pp｜VXN {cc['ndx']['vxn']}（{H['ndx_band']}）\n"
             f"SPX：振幅 A {cc['spx']['A_pct']:.2f}%｜regime 1D 超額 {cc['spx']['regime_1d_vs_base']:+.1f}pp｜VIX {cc['spx']['vix']}（{H['spx_band']}）\n"
             f"A_NDX ÷ A_SPX = {cc['A_ratio']:.2f}（長期 1.25–1.37）｜環境：{H['cross_label']}</div>")
    o.append(f'<div class="box warn">\n  {H["cross_note"]}\n</div>')
    o.append('<h2>五、新聞檢索（rule49）</h2>')
    o.append(f'<div class="box info">\n  {H["news"]}\n</div>')
    o.append('<h2>六、掛單幾何與影子帳</h2>')
    o.append('<div class="box good"><b>本日無已核准的方向 edge → 不掛實單</b>（rule57 預設休眠）</div>')
    C_ = la['close']
    o.append('<div class="tw"><table>\n<tr><th>k（×A）</th><th>多單價位</th><th>多單成交率</th><th>空單價位</th><th>空單成交率</th></tr>\n' + '\n'.join(
        f"<tr><td>{kk}</td><td>{C_ - kk * Ap:,.0f}</td><td>{FILL[kk][0]}</td><td>{C_ + kk * Ap:,.0f}</td><td>{FILL[kk][1]}</td></tr>" for kk in (0.2, 0.4, 0.6, 0.8)) + '\n</table></div>')
    pend = {x['side']: x for x in sl['pending']}
    o.append(f"<div class=\"mono\">影子單（只寫 shadow_ledger，不進主帳；隔日收盤平倉、停損優先）\n影子多：limit_buy {pend['long']['limit']:,.2f}｜停損＝成交價 −0.5A（約 −{round(0.5 * Ap)} 點）\n"
             f"影子空：limit_sell {pend['short']['limit']:,.2f}｜停損＝成交價 +0.5A（約 +{round(0.5 * Ap)} 點）\n"
             f"關鍵支撐 {' / '.join(f'{x:,}' for x in pr['key_support'])}｜關鍵壓力 {' / '.join(f'{x:,}' for x in pr['key_resistance'])}</div>")
    o.append('<h2>七、明日觀察</h2>')
    o.append('<ol>\n' + '\n'.join('<li>' + BOLD.sub(r'<b>\1</b>', w) + '</li>' for w in pr['watch_points']) + '\n</ol>')
    o.append('<h2>部位水位（部位層，不是分析）</h2>')
    o.append(f"<div class=\"box good\">\n<ul>\n<li>訊號：NDX 收盤 {pos['close']:,.2f} vs MA200 {pos['ma200']:,.2f}（{pos['pct']:+.1f}%）→ 在 MA200 {'之上' if pos['pct'] > 0 else '之下'}</li>\n"
             f"<li>水位：<b>{pos['state']}</b>（基準部位 {'100' if pos['state'] == '正常' else '50'}%）</li>\n<li>狀態：自 {pos['since']} 起維持；今日{'已' if pos['switched_today'] else '未'}切換</li>\n"
             f"<li>距切換線：收盤需再跌 {pos['dist_to_switch_pct']:.1f}% 才轉為半倉</li>\n<li>依據：prc-014（預先登記、樣本外 4/4 通過）。本段不改變上方的振幅與方向輸出。</li>\n</ul>\n</div>")
    o.append(f"<footer>\n  NDX 分析系統｜與 SPX 並列、帳本分離｜資料來源 yfinance（日線＋30 分 K）｜新聞：{H['news_sources']}<br>\n"
             '  <a href="https://johnnyhsu5509.github.io/spx-analysis/ndx/" style="color:#a78bfa">NDX</a> · <a href="https://johnnyhsu5509.github.io/spx-analysis/spx/" style="color:#22d3ee">SPX</a><br><br>\n'
             '  <b>本分析僅供學習參考，不構成投資建議。</b>\n</footer>')
    head = open(a.css, encoding='utf-8').read().replace('__DATE__', rep)
    open(a.out, 'w', encoding='utf-8', newline='\n').write(head + '<body>\n<div class="wrap">\n\n' + '\n\n'.join(o) + '\n\n</div>\n</body>\n</html>\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for x in ('--last', '--track', '--pnl', '--today', '--narrative', '--css', '--out'):
        p.add_argument(x, required=True)
    run(p.parse_args())
