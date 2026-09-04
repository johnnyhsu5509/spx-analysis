import json, yfinance as yf, pandas as pd, numpy as np

PATCH_DAYS = {"^NDX": [], "^GSPC": [], "^VXN": [],
              "QQQE": ["2026-09-03"], "QQQ": ["2026-09-03"], "SOXX": ["2026-09-03"]}


def dl(t, p="300d"):
    d = yf.download(t, period=p, progress=False, auto_adjust=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    return d


def agg30(t, day):
    d = yf.download(t, period="30d", interval="30m", progress=False, auto_adjust=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d.dropna(subset=["Close"])
    idx = pd.to_datetime(d.index)
    try:
        idx = idx.tz_convert("America/New_York")
    except Exception:
        pass
    m = d[[str(x.date()) == day for x in idx]]
    if m.empty:
        return None
    return dict(Open=float(m["Open"].iloc[0]), High=float(m["High"].max()),
                Low=float(m["Low"].min()), Close=float(m["Close"].iloc[-1]), n=len(m))


def get(t):
    """Download and repair every known gap/NaN day for this ticker."""
    d = dl(t)
    log = []
    for day in PATCH_DAYS.get(t, []):
        have = day in [str(i.date()) for i in d.index]
        isnan = have and pd.isna(d.loc[[i for i in d.index if str(i.date()) == day][0], "Close"])
        if have and not isnan:
            continue
        a = agg30(t, day)
        if a is None:
            log.append({"day": day, "status": "NO_INTRADAY"})
            continue
        vol = np.nan
        if have:
            ix = [i for i in d.index if str(i.date()) == day][0]
            vol = d.loc[ix, "Volume"]
            d = d.drop(index=ix)
        row = pd.DataFrame([{k: a[k] for k in ("Open", "High", "Low", "Close")}], index=[pd.Timestamp(day)])
        row["Volume"] = vol
        d = pd.concat([d, row]).sort_index()
        log.append({"day": day, "status": "PATCHED", "bars": a["n"], "close": round(a["Close"], 4)})
    return d.dropna(subset=["Close"]), log


def atr_pct(d, n=14):
    h, l, c = d["High"], d["Low"], d["Close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return float(tr.rolling(n).mean().iloc[-1] / c.iloc[-1] * 100)


out, plog = {}, {}
data = {}
for t in ["^NDX", "^GSPC", "QQQ", "QQQE", "SOXX", "^VXN", "^VIX", "^TNX", "DX-Y.NYB"]:
    if t in PATCH_DAYS:
        data[t], plog[t] = get(t)
    else:
        data[t] = dl(t, "90d").dropna(subset=["Close"])
out["patch_log"] = plog

ndx, spx, qqq, qqqe, soxx = data["^NDX"], data["^GSPC"], data["QQQ"], data["QQQE"], data["SOXX"]

out["ndx_atr14_pct"] = round(atr_pct(ndx), 3)
out["spx_atr14_pct"] = round(atr_pct(spx), 3)
out["atr_ratio"] = round(atr_pct(ndx) / atr_pct(spx), 3)
out["ndx_range5_pct"] = round(float(((ndx["High"]-ndx["Low"])/ndx["Close"]*100).tail(5).mean()), 3)
em = (atr_pct(ndx) + out["ndx_range5_pct"]) / 2
out["expected_move_pct"] = round(em, 3)
out["rule27_threshold_pct"] = round(em * 0.6, 3)
px = float(ndx["Close"].iloc[-1])
out["exec_band"] = [round(px*(1-em*0.6/100)), round(px*(1+em*0.6/100))]

# breadth (patched)
ratio = qqqe["Close"] / qqq["Close"]
out["breadth"] = {
    "ratio": round(float(ratio.iloc[-1]), 5),
    "chg_1d_pct": round(float((ratio.iloc[-1]/ratio.iloc[-2]-1)*100), 2),
    "chg_5d_pct": round(float((ratio.iloc[-1]/ratio.iloc[-6]-1)*100), 2),
    "vs_ma20_pct": round(float((ratio.iloc[-1]/ratio.rolling(20).mean().iloc[-1]-1)*100), 2),
    "qqqe_chg_pct": round(float(qqqe["Close"].pct_change().iloc[-1]*100), 2),
    "qqq_chg_pct": round(float(qqq["Close"].pct_change().iloc[-1]*100), 2),
    "ratio_last5": [round(float(x), 5) for x in ratio.tail(5)],
}
out["sector"] = {
    "soxx_close": round(float(soxx["Close"].iloc[-1]), 2),
    "soxx_chg_pct": round(float(soxx["Close"].pct_change().iloc[-1]*100), 2),
    "soxx_chg5_pct": round(float((soxx["Close"].iloc[-1]/soxx["Close"].iloc[-6]-1)*100), 2),
    "soxx_chg10_pct": round(float((soxx["Close"].iloc[-1]/soxx["Close"].iloc[-11]-1)*100), 2),
}
out["volume"] = {
    "qqq_vol": int(qqq["Volume"].iloc[-1]),
    "qqq_vol20": int(qqq["Volume"].tail(21).iloc[:-1].mean()),
    "qqq_vol_ratio_pct": round(float(qqq["Volume"].iloc[-1]/qqq["Volume"].tail(21).iloc[:-1].mean()*100), 1),
}
for t, k in [("^VXN","vxn"), ("^VIX","vix"), ("^TNX","tnx"), ("DX-Y.NYB","dxy")]:
    s = data[t]["Close"]
    out[k] = round(float(s.iloc[-1]), 3); out[k+"_prev"] = round(float(s.iloc[-2]), 3)
out["spx_close"] = round(float(spx["Close"].iloc[-1]), 2)
out["spx_chg_pct"] = round(float(spx["Close"].pct_change().iloc[-1]*100), 2)
out["ndx_chg_pct"] = round(float(ndx["Close"].pct_change().iloc[-1]*100), 2)
o,h,l,c = [float(ndx[x].iloc[-1]) for x in ["Open","High","Low","Close"]]
pc = float(ndx["Close"].iloc[-2])
out["candle"] = {"gap_pct": round((o-pc)/pc*100,3), "close_pos_pct": round((c-l)/(h-l)*100,1),
                 "upper_wick": round(h-max(o,c),1), "lower_wick": round(min(o,c)-l,1),
                 "body": round(c-o,1), "range_pts": round(h-l,1), "range_pct": round((h-l)/c*100,3)}
# RSI window artefact check
dd = ndx["Close"].diff()
out["rsi_window"] = {"drop_out_date": str(dd.index[-15].date()),
                     "drop_out_chg": round(float(dd.iloc[-15]),2),
                     "new_bar_chg": round(float(dd.iloc[-1]),2)}
with open("ndx_aux_0904.txt","w",encoding="utf-8") as f:
    json.dump(out,f,indent=2,ensure_ascii=False)
print("OK")
