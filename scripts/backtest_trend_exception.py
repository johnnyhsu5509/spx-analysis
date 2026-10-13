"""NDX 趨勢例外（方案 A）＋過熱因子打折（方案 B）回測。輸出 backtest_trend_exception.txt（UTF-8）。"""
import json
import numpy as np
import pandas as pd
import yfinance as yf

d = yf.download("^NDX", start="2009-01-01", progress=False, auto_adjust=False)
if isinstance(d.columns, pd.MultiIndex):
    d.columns = d.columns.get_level_values(0)
d = d.dropna(subset=["Open", "High", "Low", "Close"])
o, h, l, c = d["Open"], d["High"], d["Low"], d["Close"]

for n in (5, 20, 50, 200):
    d[f"ma{n}"] = c.rolling(n).mean()
delta = c.diff()
d["rsi"] = 100 - 100 / (1 + delta.clip(lower=0).rolling(14).mean() / (-delta.clip(upper=0)).rolling(14).mean())
macd = c.ewm(span=12).mean() - c.ewm(span=26).mean()
d["mh"] = macd - macd.ewm(span=9).mean()
mid, sd = c.rolling(20).mean(), c.rolling(20).std()
d["bbp"] = (c - (mid - 2 * sd)) / (4 * sd) * 100
tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
d["atr"] = tr.rolling(14).mean()
d["atr_pct"] = d["atr"] / c * 100
d["rng5"] = ((h - l) / c * 100).rolling(5).mean()
d["thr"] = (d["atr_pct"] + d["rng5"]) / 2 * 0.6
d["prior_hi20"] = c.shift(1).rolling(20).max()
d["stk"] = (d.ma5 > d.ma20) & (d.ma20 > d.ma50) & (d.ma50 > d.ma200)
d["breakout"] = c >= c.rolling(20).max()
d["macd_up"] = (d.mh > 0) & (d.mh > d.mh.shift(1))
d["trend"] = d.stk & d.breakout & d.macd_up
d["overheat"] = (d.rsi > 70) | (d.bbp > 100) | (c / d.ma200 - 1 > 0.10)
d["next_ret"] = c.shift(-1) / c - 1
d["fwd5_low"] = l.shift(-1)[::-1].rolling(5, min_periods=5).min()[::-1] / c - 1
d = d.loc["2010-01-01":]

STOP_ATR, T1_ATR = 0.5, 0.6


def sim(i, kind):
    """回傳 (status, pnl_atr, pnl_pct)；i 為訊號日位置，判定 i+1。"""
    if i + 1 >= len(d):
        return None
    s, n = d.iloc[i], d.iloc[i + 1]
    atr = s.atr
    if kind == "pullback":
        entry = s.prior_hi20
        if not np.isfinite(entry) or (s.Close - entry) / s.Close * 100 > s.thr or entry >= s.Close:
            return ("SKIP_RULE27", 0, 0)
        stop, t1 = entry - STOP_ATR * atr, entry + T1_ATR * atr
        if n.Open <= stop:
            return ("GAP_INVALID", 0, 0)
        if n.Low > entry:
            return ("NOT_FILLED", 0, 0)
        fill = entry
    else:
        entry = s.High * 1.0005
        if (entry - s.Close) / s.Close * 100 > s.thr:
            return ("SKIP_RULE27", 0, 0)
        if n.High < entry:
            return ("NOT_FILLED", 0, 0)
        fill = max(entry, n.Open)
        stop, t1 = fill - STOP_ATR * atr, fill + T1_ATR * atr
        if n.Open >= t1:
            return ("GAP_INVALID", 0, 0)
    if n.Low <= stop:
        px = stop
    elif n.High >= t1:
        px = t1
    else:
        px = n.Close
    return ("FILLED", (px - fill) / atr, (px - fill) / fill * 100)


def stats(mask, kind):
    rows = [sim(d.index.get_loc(ix), kind) for ix in d.index[mask]]
    rows = [r for r in rows if r]
    f = [r for r in rows if r[0] == "FILLED"]
    st = {k: sum(1 for r in rows if r[0] == k) for k in ("FILLED", "NOT_FILLED", "SKIP_RULE27", "GAP_INVALID")}
    if not f:
        return {"signals": len(rows), **st}
    a = np.array([r[1] for r in f]); p = np.array([r[2] for r in f])
    return {"signals": len(rows), **st, "win_pct": round((a > 0).mean() * 100, 1),
            "avg_atr": round(a.mean(), 3), "avg_pct": round(p.mean(), 3), "sum_pct": round(p.sum(), 2),
            "t_stat": round(a.mean() / (a.std(ddof=1) / np.sqrt(len(a))), 2) if len(a) > 1 else None}


def fwd(mask):
    x = d[mask].dropna(subset=["next_ret", "fwd5_low"])
    r = x.next_ret * 100
    return {"n": len(x), "up_pct": round((r >= 0.4).mean() * 100, 1), "down_pct": round((r <= -0.4).mean() * 100, 1),
            "avg_next_pct": round(r.mean(), 3), "pullback5d_pct": round((x.fwd5_low <= -0.01).mean() * 100, 1)}


out = {"sample": f"{d.index[0].date()} – {d.index[-1].date()}", "days": len(d),
       "params": {"stop_atr": STOP_ATR, "t1_atr": T1_ATR, "trend": "四線多頭排列 & 收盤創20日新高 & MACD柱>0且放大",
                  "overheat": "RSI(SMA)>70 或 %B>100 或 距MA200>10%", "horizon": "1日（未觸價收盤平倉）",
                  "same_day": "停損與T1同日皆觸及→保守判停損"}}
periods = {"全期": slice(None), "2010-2018": slice("2010", "2018"), "2019-2026": slice("2019", "2026")}
A = {}
for pname, sl in periods.items():
    sub = pd.Series(False, index=d.index); sub.loc[sl] = True
    A[pname] = {}
    for kind in ("pullback", "breakout"):
        A[pname][kind] = {
            "trend_days": stats(sub & d.trend, kind),
            "stack_no_breakout": stats(sub & d.stk & ~d.trend, kind),
            "all_days": stats(sub, kind),
            "trend_overheat": stats(sub & d.trend & d.overheat, kind),
            "trend_not_overheat": stats(sub & d.trend & ~d.overheat, kind),
        }
out["A_trend_exception"] = A
out["trend_day_freq_pct"] = round(d.trend.mean() * 100, 1)

B = {"baseline_all": fwd(d.index == d.index)}
for nm, m in {"uptrend_overheat": d.stk & d.overheat, "uptrend_not_overheat": d.stk & ~d.overheat,
              "not_uptrend_overheat": ~d.stk & d.overheat, "not_uptrend_not_overheat": ~d.stk & ~d.overheat,
              "rsi70_in_uptrend": d.stk & (d.rsi > 70), "bb100_in_uptrend": d.stk & (d.bbp > 100),
              "ma200_10pct_in_uptrend": d.stk & (c.loc[d.index] / d.ma200 - 1 > 0.10),
              "rsi70_not_uptrend": ~d.stk & (d.rsi > 70)}.items():
    B[nm] = fwd(m)
for pname, sl in list(periods.items())[1:]:
    sub = pd.Series(False, index=d.index); sub.loc[sl] = True
    B[pname] = {"base": fwd(sub), "uptrend_overheat": fwd(sub & d.stk & d.overheat),
                "uptrend_not_overheat": fwd(sub & d.stk & ~d.overheat)}
out["B_overheat_in_uptrend"] = B

recent = d.loc["2026-09-15":, ["Close", "stk", "breakout", "macd_up", "trend", "overheat", "rsi", "bbp"]]
out["recent_flags"] = {str(ix.date()): {"close": round(r.Close, 1), "trend": bool(r.trend), "stack": bool(r.stk),
                                         "breakout": bool(r.breakout), "macd_up": bool(r.macd_up),
                                         "overheat": bool(r.overheat), "rsi": round(r.rsi, 1)} for ix, r in recent.iterrows()}
out["recent_trades"] = {str(ix.date()): {k: sim(d.index.get_loc(ix), k) for k in ("pullback", "breakout")}
                        for ix in recent.index[recent.trend]}
json.dump(out, open("backtest_trend_exception.txt", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)


def hold(mask, n, stop_atr=None):
    res = []
    idx = list(d.index)
    for ix in d.index[mask]:
        i = idx.index(ix)
        if i + n >= len(d):
            continue
        s = d.iloc[i]; e = d.iloc[i + 1].Open
        px = d.iloc[i + n].Close
        if stop_atr:
            stop = e - stop_atr * s.atr
            for j in range(i + 1, i + n + 1):
                r = d.iloc[j]
                if r.Open <= stop:
                    px = r.Open; break
                if r.Low <= stop:
                    px = stop; break
        res.append((px - e) / e * 100)
    a = np.array(res)
    return {"n": len(a), "win_pct": round((a > 0).mean() * 100, 1), "avg_pct": round(a.mean(), 3),
            "median_pct": round(float(np.median(a)), 3), "t": round(a.mean() / (a.std(ddof=1) / np.sqrt(len(a))), 2)}


H = {}
for pname, sl in periods.items():
    sub = pd.Series(False, index=d.index); sub.loc[sl] = True
    H[pname] = {}
    for n in (1, 3, 5, 10):
        H[pname][f"{n}d"] = {"trend": hold(sub & d.trend, n), "trend_stop1atr": hold(sub & d.trend, n, 1.0),
                              "all_days": hold(sub, n), "stack_any": hold(sub & d.stk, n),
                              "trend_overheat": hold(sub & d.trend & d.overheat, n)}
out["H_multi_day_hold"] = H
json.dump(out, open("backtest_trend_exception.txt", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
