import json, yfinance as yf, pandas as pd, numpy as np

def dl(t, p="300d"):
    d = yf.download(t, period=p, progress=False, auto_adjust=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    return d.dropna(subset=["Close"])

def atr_pct(d, n=14):
    h, l, c = d["High"], d["Low"], d["Close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return float(tr.rolling(n).mean().iloc[-1] / c.iloc[-1] * 100)

def rng5(d):
    return float(((d["High"] - d["Low"]) / d["Close"] * 100).tail(5).mean())

def rsi_sma(c, n=14):
    dl_ = c.diff()
    g = dl_.clip(lower=0).rolling(n).mean()
    ls = (-dl_.clip(upper=0)).rolling(n).mean()
    return 100 - 100 / (1 + g / ls)

out = {}
ndx = dl("^NDX"); spx = dl("^GSPC"); qqq = dl("QQQ"); soxx = dl("SOXX"); qqqe = dl("QQQE")

out["ndx_atr14_pct"] = round(atr_pct(ndx), 3)
out["spx_atr14_pct"] = round(atr_pct(spx), 3)
out["atr_ratio_ndx_spx"] = round(atr_pct(ndx) / atr_pct(spx), 3)
out["ndx_range5_pct"] = round(rng5(ndx), 3)
em = (atr_pct(ndx) + rng5(ndx)) / 2
out["expected_move_pct"] = round(em, 3)
out["rule27_threshold_pct"] = round(em * 0.6, 3)
px = float(ndx["Close"].iloc[-1])
out["exec_band"] = [round(px * (1 - em * 0.6 / 100)), round(px * (1 + em * 0.6 / 100))]

# rule36 volume integrity
for nm, d in [("ndx", ndx), ("spx", spx), ("qqq", qqq)]:
    v = d["Volume"]
    out[nm + "_vol"] = int(v.iloc[-1])
    out[nm + "_vol20"] = int(v.tail(21).iloc[:-1].mean())
    out[nm + "_vol_ratio_pct"] = round(v.iloc[-1] / v.tail(21).iloc[:-1].mean() * 100, 1)

# RSI trace (SMA/Cutler) - why it rose while price fell
r = rsi_sma(ndx["Close"])
out["ndx_rsi_last3"] = [round(float(x), 2) for x in r.tail(3)]
d14 = ndx["Close"].diff()
out["drop_out_bar_date"] = str(d14.index[-15].date())
out["drop_out_bar_chg"] = round(float(d14.iloc[-15]), 2)
out["new_bar_chg"] = round(float(d14.iloc[-1]), 2)

# SPX today
out["spx_close"] = round(float(spx["Close"].iloc[-1]), 2)
out["spx_chg_pct"] = round(float(spx["Close"].pct_change().iloc[-1] * 100), 2)
out["spx_rsi_sma"] = round(float(rsi_sma(spx["Close"]).iloc[-1]), 2)
out["spx_date"] = str(spx.index[-1].date())

# SOXX / QQQE
for nm, d in [("soxx", soxx), ("qqqe", qqqe)]:
    out[nm + "_close"] = round(float(d["Close"].iloc[-1]), 2)
    out[nm + "_chg_pct"] = round(float(d["Close"].pct_change().iloc[-1] * 100), 2)
    out[nm + "_chg5_pct"] = round(float((d["Close"].iloc[-1] / d["Close"].iloc[-6] - 1) * 100), 2)
    out[nm + "_date"] = str(d.index[-1].date())
out["qqq_chg_pct"] = round(float(qqq["Close"].pct_change().iloc[-1] * 100), 2)
out["ndx_date"] = str(ndx.index[-1].date())

# gap / candle anatomy
o, h, l, c = [float(ndx[k].iloc[-1]) for k in ["Open", "High", "Low", "Close"]]
pc = float(ndx["Close"].iloc[-2])
out["gap_pct"] = round((o - pc) / pc * 100, 2)
out["close_pos_in_range_pct"] = round((c - l) / (h - l) * 100, 1)
out["upper_wick_pts"] = round(h - max(o, c), 1)
out["lower_wick_pts"] = round(min(o, c) - l, 1)
out["body_pts"] = round(abs(c - o), 1)

with open("ndx_aux_0818.txt", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print("OK")
