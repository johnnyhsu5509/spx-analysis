"""NDX 每日輔助數據：一支帶參數的腳本，取代每天複製一份的 _ndx_aux_MMDD.py。

  python3 scripts/ndx_aux.py [--today scripts/ndx_today_data.txt] [--spx-last docs/last_analysis.json] [--out scripts/ndx_aux.json]

輸出直接當 daily_run.py 的 --aux：volatility_scale／breadth／sector／macro 四塊（原樣搬進 ndx_last_analysis），外加
  facts    模型原本手算的數字：跳空、收盤位置、量比、均線斜率與交叉、連續天數、費波回撤、60 日新高低、宏觀前值、30 分 K
  futures  NQ／ES 最新價對資料日結算的漲跌，並換算成幾個 A（隱含開盤距前收 ÷ A）
  spx_news SPX 同一資料日已做過的新聞檢索（rule49 共用；SPX 還沒跑或基準日不同就是 null）
每一條序列都截到資料日為止（週日晚間期貨盤的新列不會被當成資料日的值）；截完最後一列不是資料日的，列進 facts.stale。
指標（RSI／MACD／布林／KD）不在這裡重算（rule33），一律讀 ndx_today_data.txt。不 print 中文。
"""
import argparse
import io
import json
import os
import urllib.request

import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
FIB = (0.236, 0.382, 0.5, 0.618)
CBOE_VXN = 'https://cdn.cboe.com/api/global/us_indices/daily_prices/VXN_History.csv'
MACRO = (('tnx', '^TNX'), ('vix', '^VIX'), ('vxn', '^VXN'), ('dxy', 'DX-Y.NYB'), ('wti', 'CL=F'), ('brent', 'BZ=F'))


def dl(t, period='60d', interval='1d'):
    d = yf.download(t, period=period, interval=interval, progress=False, auto_adjust=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    return d.dropna(subset=['Close'])


def vxn_close(period, day, src):
    """^VXN 收盤序列（截到資料日）。Yahoo 沒更新到資料日時，缺的日子用 Cboe 官方每日歷史檔補上（與 fetch_today.py 同一來源），補了哪幾天記進 src。"""
    x = cut(dl('^VXN', period), day)['Close']
    last = str(x.index[-1].date())
    if last >= day:
        return x
    try:
        req = urllib.request.Request(CBOE_VXN, headers={'User-Agent': 'Mozilla/5.0'})
        c = pd.read_csv(io.StringIO(urllib.request.urlopen(req, timeout=25).read().decode('utf-8')))
        c.index = pd.to_datetime(c['DATE'], format='%m/%d/%Y')
        k = c.index.strftime('%Y-%m-%d')
        add = c[(k > last) & (k <= day)]['CLOSE'].dropna().astype(float)
        if add.empty or str(add.index[-1].date()) != day:
            return x
        if x.index.tz is not None:
            add.index = add.index.tz_localize(x.index.tz)
        src[:] = [str(d.date()) for d in add.index]
        return pd.concat([x, add]).sort_index()
    except Exception:
        return x


def cut(d, day):
    return d[d.index.strftime('%Y-%m-%d') <= day]


def streak(flags):
    n = 0
    for f in reversed(list(flags)):
        if not f:
            break
        n += 1
    return n


def fib(h, l, day):
    """近 60 個交易日的最高點與其後最低點（下跌段）；最高點就在資料日時改取其前最低點（上漲段）。回撤位從波段終點往回算。"""
    w = h.tail(60)
    hi_d = w.idxmax()
    if str(hi_d.date()) < day:
        seg = l[l.index >= hi_d]
        lo_d, kind = seg.idxmin(), 'down'
        hi, lo = float(w.max()), float(seg.min())
        lv = {f'r{int(f * 1000)}': round(lo + f * (hi - lo)) for f in FIB}
    else:
        seg = l.tail(60)
        lo_d, kind = seg.idxmin(), 'up'
        hi, lo = float(w.max()), float(seg.min())
        lv = {f'r{int(f * 1000)}': round(hi - f * (hi - lo)) for f in FIB}
    return {'kind': kind, 'high': round(hi, 2), 'high_date': str(hi_d.date()), 'low': round(lo, 2), 'low_date': str(lo_d.date()), **lv}


BUF = 0.02


def regime_shadow(c, ma50, ma200):
    """市場狀態標籤＋影子水位（2026-11-26 核准「加進報告當影子記錄」；回測見 100_Todo/projects/ndx_regime_staged_backtest_20261126）。
    只讀價格、從頭重播，不存狀態、不寫帳本；不取代 prc-014 的現行水位。
    影子水位：收盤 < MA200×0.98 → 50%，收盤 > MA200×1.02 → 100%，中間維持前一日；50% 期間若收盤在 MA200 下且
    （MA200 低於 20 日前 或 MA50 < MA200）→ 25%。
    狀態：熊市＝收盤在 MA200 下且（MA200 低於 20 日前 或 距一年高 ≤ −20%）；多頭＝收盤 > MA200×1.02 且距一年高 > −8%；其餘為修正。"""
    hi = c.rolling(252, min_periods=60).max()
    dd = (c / hi - 1) * 100
    half, state, rows = None, None, []
    for i in range(len(c)):
        m, x = ma200.iloc[i], float(c.iloc[i])
        if m != m:
            continue
        m = float(m)
        down = m < float(ma200.iloc[i - 20]) if ma200.iloc[i - 20] == ma200.iloc[i - 20] else False
        death = float(ma50.iloc[i]) < m
        if half is None:
            half, state = x < m, ('修正' if x < m or dd.iloc[i] <= -10 else '多頭')
        if x < m * (1 - BUF):
            half = True
        elif x > m * (1 + BUF):
            half = False
        pct = 25 if (half and x < m and (down or death)) else 50 if half else 100
        if x < m and (down or dd.iloc[i] <= -20):
            state = '熊市'
        elif x > m * (1 + BUF) and dd.iloc[i] > -8:
            state = '多頭'
        elif x < m or dd.iloc[i] <= -10 or state == '熊市':
            state = '修正'
        rows.append((str(c.index[i].date()), state, pct, down, death))
    day, state, pct, down, death = rows[-1]
    since = next(r[0] for k, r in enumerate(rows) if all(q[1] == state for q in rows[k:]))
    psince = next(r[0] for k, r in enumerate(rows) if all(q[2] == pct for q in rows[k:]))
    x, m, h = float(c.iloc[-1]), float(ma200.iloc[-1]), float(hi.iloc[-1])
    slope = (m / float(ma200.iloc[-21]) - 1) * 100
    gap = (float(ma50.iloc[-1]) / m - 1) * 100
    f = lambda v: f'{v:,.0f}'
    md = lambda d: f'{int(d[5:7])}/{int(d[8:10])}'
    line = (f"市場狀態：{state}（自 {md(since)}）｜距一年高點 {dd.iloc[-1]:+.1f}%、距 200 日線 {(x / m - 1) * 100:+.1f}%、"
            f"200 日線{'下彎' if down else '仍上升'}（20 日 {slope:+.1f}%）、50 日線{'已跌破' if death else '高於'} 200 日線（{gap:+.1f}%）")
    line2 = (f"影子水位（往下一段＋2% 緩衝，只記錄、不是現行規則）：{pct}%（自 {md(psince)}）｜"
             f"減到 25%：收盤在 200 日線下且 200 日線下彎或 50 日線跌破 200 日線｜加回 100%：收盤 > {f(m * (1 + BUF))}｜"
             f"狀態轉熊市：收盤 ≤ {f(h * 0.8)}（距高點 −20%）或 200 日線下彎")
    return {'as_of': day, 'state': state, 'state_since': since, 'shadow_target_pct': pct, 'shadow_since': psince,
            'dd_from_1y_high_pct': round(float(dd.iloc[-1]), 2), 'high_1y': round(h, 2), 'ma200': round(m, 2),
            'ma200_20d_chg_pct': round(slope, 2), 'ma200_falling': bool(down), 'ma50_vs_ma200_pct': round(gap, 2), 'death_cross': bool(death),
            'levels': {'bear_if_close_le': round(h * 0.8), 'shadow_100_if_close_gt': round(m * (1 + BUF)), 'shadow_50_if_close_lt': round(m * (1 - BUF))},
            'line': line, 'line_shadow': line2,
            'note': '固定定義、由價格重播得出；狀態描述風險環境，不預測方向（歷史上熊市狀態之後 60 日上漲仍占 61%，但最差一成為 −24.5%）。影子水位不取代現行部位水位（prc-014）'}


def build(td, spx=None):
    if td.get('symbol') != 'NDX':
        raise SystemExit('today_data 不是 NDX')
    day, C, am = td['trade_date'], td['close'], td['amplitude']
    stale = []
    n = cut(dl('^NDX', '400d'), day)
    if str(n.index[-1].date()) != day or abs(float(n['Close'].iloc[-1]) - C) > 0.01:
        raise SystemExit(f'^NDX 日線最後一列 {n.index[-1].date()} 與 today_data {day}／收盤對不上')
    o, h, l, c, v = (n[k] for k in ('Open', 'High', 'Low', 'Close', 'Volume'))
    ma = {k: c.rolling(k).mean() for k in (5, 20, 50, 200)}
    if abs(float(ma[200].iloc[-1]) - td['ma200']) > 0.01:
        raise SystemExit('MA200 與 today_data 不一致')
    vol20 = float(v.iloc[-21:-1].mean())
    px, p0 = float(c.iloc[-1]), float(c.iloc[-2])
    facts = {
        'gap_pct': round((float(o.iloc[-1]) - p0) / p0 * 100, 3),
        'close_pos_pct': round((px - float(l.iloc[-1])) / (float(h.iloc[-1]) - float(l.iloc[-1])) * 100, 1),
        'range_pct': round((float(h.iloc[-1]) - float(l.iloc[-1])) / p0 * 100, 3),
        'ndx_vol_ratio_pct': round(float(v.iloc[-1]) / vol20 * 100, 1),
        'ma_slope_pts': {f'ma{k}': round(float(ma[k].diff().iloc[-1]), 1) for k in ma},
        'streak_days': {'close_below_ma200': streak(c < ma[200]), 'close_above_ma200': streak(c > ma[200]),
                        'ma20_below_ma50': streak(ma[20] < ma[50]), 'ma20_below_ma200': streak(ma[20] < ma[200])},
        'low_60d': bool(l.iloc[-1] <= l.tail(60).min()), 'high_60d': bool(h.iloc[-1] >= h.tail(60).max()),
        'prev_day': {'date': str(n.index[-2].date()), 'high': round(float(h.iloc[-2]), 2), 'low': round(float(l.iloc[-2]), 2)},
        'fib': fib(h, l, day),
    }
    facts['rule36_triggered'] = facts['ndx_vol_ratio_pct'] < 30
    try:
        q = cut(dl('QQQ'), day)
        if str(q.index[-1].date()) == day:
            facts['qqq'] = {'chg_pct': round(float(q['Close'].pct_change().iloc[-1] * 100), 2),
                            'vol_ratio_pct': round(float(q['Volume'].iloc[-1]) / float(q['Volume'].iloc[-21:-1].mean()) * 100, 1)}
        else:
            stale.append(f'QQQ@{q.index[-1].date()}')
        e = cut(dl('QQQE'), day)
        if str(e.index[-1].date()) == day:
            facts['qqqe_chg_pct'] = round(float(e['Close'].pct_change().iloc[-1] * 100), 2)
        else:
            stale.append(f'QQQE@{e.index[-1].date()}')
    except Exception as ex:
        stale.append(f'QQQ/QQQE:{type(ex).__name__}')
    macro, moves, vsrc = {}, {}, []
    for k, t in MACRO:
        try:
            x = vxn_close('20d', day, vsrc) if t == '^VXN' else cut(dl(t, '20d'), day)['Close']
            if str(x.index[-1].date()) != day:
                stale.append(f'{k}@{x.index[-1].date()}')
            macro[k] = round(float(x.iloc[-1]), 3)
            moves[k] = {'prev': round(float(x.iloc[-2]), 3), 'last': macro[k], 'chg_pct': round(float((x.iloc[-1] / x.iloc[-2] - 1) * 100), 2)}
        except Exception as ex:
            macro[k] = None
            stale.append(f'{k}:{type(ex).__name__}')
    facts['macro_moves'] = moves
    try:
        vx = vxn_close('60d', day, vsrc)
        facts['streak_days']['vxn_ge28'] = streak(vx >= 28)
    except Exception:
        pass
    try:
        m = dl('^NDX', '7d', '30m')
        idx = m.index.tz_convert('America/New_York')
        facts['bars30'] = [[str(i)[11:16], round(float(r.Open), 1), round(float(r.High), 1), round(float(r.Low), 1), round(float(r.Close), 1)]
                           for i, r in zip(idx, m.itertuples()) if str(i.date()) == day]
    except Exception as ex:
        facts['bars30'] = []
        stale.append(f'bars30:{type(ex).__name__}')
    futures = {}
    for k, t in (('nq', 'NQ=F'), ('es', 'ES=F')):
        try:
            x = dl(t, '10d')['Close']
            base = cut(x.to_frame(), day)['Close']
            if str(base.index[-1].date()) != day:
                futures[k] = None
                continue
            pct = (float(x.iloc[-1]) / float(base.iloc[-1]) - 1) * 100
            new = str(x.index[-1].date()) > day
            futures[k] = {'settle': round(float(base.iloc[-1]), 2), 'last': round(float(x.iloc[-1]), 2), 'last_date': str(x.index[-1].date()),
                          'chg_pct': round(pct, 2) if new else None}
        except Exception:
            futures[k] = None
    nq = futures.get('nq')
    if nq and nq['chg_pct'] is not None:
        futures['implied_open_in_A'] = round(nq['chg_pct'] / am['amp_forecast_pct'], 2)
        futures['implied_open_approx'] = round(C * (1 + nq['chg_pct'] / 100), 1)
        futures['method'] = 'NQ 最新日線列 ÷ 資料日結算（近似；結算在 17:00 ET，現貨收盤在 16:00 ET）'
    else:
        futures['implied_open_in_A'] = None
    facts['stale'] = stale
    try:
        shadow = regime_shadow(c, ma[50], ma[200])
    except Exception as ex:
        shadow = None
        stale.append(f'regime_shadow:{type(ex).__name__}')
    if vsrc:
        facts['vxn_source'] = {'source': 'Cboe official daily history (VXN_History.csv)', 'days': vsrc}
    br, sm, sd = td.get('breadth') or {}, td.get('semis_daily') or {}, td.get('sector_daily') or {}
    news = None
    if spx and spx.get('data_basis', '').startswith(day):
        news = {'catalysts': spx.get('catalysts'), 'news_check': spx.get('news_check'), 'event_day': spx.get('event_day')}
    return {
        'trade_date': day,
        'volatility_scale': {'atr14_pct': am['atr14_pct'], 'range5_pct': round(float(((h - l) / c * 100).tail(5).mean()), 3)},
        'breadth': {**{k: br.get(k) for k in ('qqqe_qqq_ratio', 'chg_1d_pct', 'chg_5d_pct', 'vs_ma20_pct')},
                    'tail_source': 'daily' if br.get('as_of') == day else f"stale:{br.get('as_of')}"},
        'sector': {'sox_close': sm.get('close'), 'sox_chg_pct': sm.get('change_pct'), 'sox_5d_pct': sm.get('chg_5d_pct'),
                   'soxx_chg_pct': (sd.get('SOXX') or {}).get('change_pct'), 'smh_chg_pct': (sd.get('SMH') or {}).get('change_pct')},
        'macro': macro, 'facts': facts, 'futures': futures, 'spx_news': news, 'regime_shadow': shadow,
    }


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--today', default=os.path.join(HERE, 'ndx_today_data.txt'))
    p.add_argument('--spx-last', default=os.path.join(os.path.dirname(HERE), 'docs', 'last_analysis.json'))
    p.add_argument('--out', default=os.path.join(HERE, 'ndx_aux.json'))
    a = p.parse_args(argv)
    with open(a.today, encoding='utf-8') as f:
        td = json.load(f)
    spx = None
    if os.path.exists(a.spx_last):
        with open(a.spx_last, encoding='utf-8') as f:
            spx = json.load(f)
    with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(build(td, spx), f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
