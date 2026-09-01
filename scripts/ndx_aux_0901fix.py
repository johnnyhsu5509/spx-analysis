import json, yfinance as yf, pandas as pd, numpy as np

def dl(t, p="300d"):
    d = yf.download(t, period=p, progress=False, auto_adjust=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    return d.dropna(subset=["Close"])

def agg30(t, day):
    """Rebuild a missing daily bar from 30m intraday bars (same method as gap_fix.py)."""
    d = yf.download(t, period="60d", interval="30m", progress=False, auto_adjust=False)
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

def patch(d, t, day):
    if day in [str(i.date()) for i in d.index]:
        return d, None
    a = agg30(t, day)
    if a is None:
        return d, None
    row = pd.DataFrame([{k: a[k] for k in ("Open", "High", "Low", "Close")}],
                       index=[pd.Timestamp(day)])
    row["Volume"] = np.nan
    d2 = pd.concat([d, row]).sort_index()
    return d2, a

def atr_pct(d, n=14):
    h, l, c = d["High"], d["Low"], d["Close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return float(tr.rolling(n).mean().iloc[-1] / c.iloc[-1] * 100)

def rng5(d):
    return float(((d["High"] - d["Low"]) / d["Close"] * 100).tail(5).mean())

out = {}
ndx, pn = patch(dl("^NDX"), "^NDX", "2026-08-28")
spx, ps = patch(dl("^GSPC"), "^GSPC", "2026-08-28")
out["patch_ndx_0828"] = pn
out["patch_spx_0828"] = ps

out["ndx_atr14_pct"] = round(atr_pct(ndx), 3)
out["spx_atr14_pct"] = round(atr_pct(spx), 3)
out["atr_ratio"] = round(atr_pct(ndx) / atr_pct(spx), 3)
out["ndx_range5_pct"] = round(rng5(ndx), 3)
em = (atr_pct(ndx) + rng5(ndx)) / 2
out["expected_move_pct"] = round(em, 3)
out["rule27_threshold_pct"] = round(em * 0.6, 3)
px = float(ndx["Close"].iloc[-1])
out["px"] = round(px, 2)
out["exec_band"] = [round(px * (1 - em * 0.6 / 100)), round(px * (1 + em * 0.6 / 100))]
out["ndx_last6"] = [(str(i.date()), round(float(v), 2)) for i, v in ndx["Close"].tail(6).items()]
out["spx_last4"] = [(str(i.date()), round(float(v), 2)) for i, v in spx["Close"].tail(4).items()]
out["spx_chg_pct"] = round(float(spx["Close"].pct_change().iloc[-1] * 100), 2)
out["ndx_chg_pct"] = round(float(ndx["Close"].pct_change().iloc[-1] * 100), 2)
out["ndx_gap_pct"] = round(float((ndx["Open"].iloc[-1] / ndx["Close"].iloc[-2] - 1) * 100), 3)

with open("ndx_aux_0901fix.txt", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print("OK")
