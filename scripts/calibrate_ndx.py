# -*- coding: utf-8 -*-
"""VXN threshold calibration for the NDX analysis system.

Do NOT reuse the SPX VIX cuts (16 / 20) on VXN. This script derives NDX cuts
three independent ways and writes them to calib_ndx.txt for review:

  1. percentile mapping  - VXN value sitting at the same historical percentile
                           as VIX 16 / VIX 20
  2. spread statistics   - actual VXN-VIX spread distribution (checks the
                           "3-5 points higher" rule of thumb)
  3. empirical sweep     - grid search over candidate cuts, scored by how well
                           they separate realised 5D pullback rates

Also reports NDX vs SPX realised volatility so the pullback threshold itself
can be scaled (a -0.75% move is not the same event on NDX as on SPX).

ASCII-only stdout (cp950 safe). Results land in calib_ndx.txt.
"""
import json
import os
from datetime import datetime

import yf_compat

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

PCT_START = "2006-01-01"   # long window: stable percentiles
BT_START = "2021-01-01"    # short window: matches SPX backtest.py for comparability
PULLBACK = 0.0075          # SPX-comparable definition
HORIZONS = [1, 3, 5]


def flat(df):
    if df is not None and hasattr(df.columns, "levels"):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def dl(sym, start):
    df = flat(yf_compat.download(sym, start=start, progress=False))
    if df is None or df.empty:
        raise SystemExit("FETCH FAILED: empty dataframe for " + sym)
    return df


def pct_of(series, value):
    """Percentile rank of `value` within `series`."""
    s = series.dropna()
    return float((s < value).sum()) / len(s) * 100.0


def value_at(series, pct):
    """Value sitting at percentile `pct`."""
    return float(series.dropna().quantile(pct / 100.0))


# ---------------------------------------------------------------- 1. percentiles
vix_long = dl("^VIX", PCT_START)["Close"].squeeze()
vxn_long = dl("^VXN", PCT_START)["Close"].squeeze()

common = vix_long.index.intersection(vxn_long.index)
vix_c = vix_long.reindex(common).dropna()
vxn_c = vxn_long.reindex(common).dropna()
common = vix_c.index.intersection(vxn_c.index)
vix_c, vxn_c = vix_c.reindex(common), vxn_c.reindex(common)

pct16 = pct_of(vix_c, 16.0)
pct20 = pct_of(vix_c, 20.0)
map_lo = value_at(vxn_c, pct16)
map_hi = value_at(vxn_c, pct20)

# ---------------------------------------------------------------- 2. spread
spread = (vxn_c - vix_c).dropna()
ratio = (vxn_c / vix_c).dropna()

# ---------------------------------------------------------------- 3. backtest data
ndx = dl("^NDX", BT_START)
spx = dl("^GSPC", BT_START)
vxn_bt = dl("^VXN", BT_START)["Close"].squeeze()

nclose, nlow = ndx["Close"].squeeze(), ndx["Low"].squeeze()
sclose, slow = spx["Close"].squeeze(), spx["Low"].squeeze()
ma20 = nclose.rolling(20).mean()
ma200 = nclose.rolling(200).mean()
vxn_b = vxn_bt.reindex(nclose.index).ffill()

# realised vol comparison (drives whether PULLBACK should be scaled)
nret = nclose.pct_change().dropna()
sret = sclose.pct_change().dropna()
vol_ratio = float(nret.std() / sret.std())


def build_cases(close, low, pullback):
    n, maxH = len(close), max(HORIZONS)
    out = []
    for i in range(n):
        c, m20, m200, v = close.iloc[i], ma20.iloc[i], ma200.iloc[i], vxn_b.iloc[i]
        if any(x != x for x in (m20, m200, v)):
            continue
        if i + maxH >= n:
            continue
        row = {"date": str(close.index[i].date()), "vxn": float(v),
               "trend": "above_ma200" if c >= m200 else "below_ma200",
               "ext": "ma20_over3" if (c - m20) / m20 * 100 >= 3
                      else ("ma20_under3" if (c - m20) / m20 * 100 <= -3 else "ma20_normal")}
        for h in HORIZONS:
            row["hit_%d" % h] = 1 if low.iloc[i + 1:i + 1 + h].min() <= c * (1 - pullback) else 0
        out.append(row)
    return out


cases_raw = build_cases(nclose, nlow, PULLBACK)                  # same def as SPX
cases_scaled = build_cases(nclose, nlow, PULLBACK * vol_ratio)   # vol-adjusted


def rate(sub, key):
    return sum(c[key] for c in sub) / len(sub) * 100 if sub else float("nan")


def sweep(cases, key="hit_5"):
    """Grid search cut pairs; score = spread between extreme bucket rates,
    requiring every bucket to hold at least 12% of the sample."""
    best, table = None, []
    lo_grid = [x * 0.5 for x in range(36, 55)]   # 18.0 .. 27.0
    hi_grid = [x * 0.5 for x in range(44, 71)]   # 22.0 .. 35.0
    for lo in lo_grid:
        for hi in hi_grid:
            if hi <= lo + 1.5:
                continue
            a = [c for c in cases if c["vxn"] < lo]
            b = [c for c in cases if lo <= c["vxn"] < hi]
            d = [c for c in cases if c["vxn"] >= hi]
            m = min(len(a), len(b), len(d))
            if m < len(cases) * 0.12:
                continue
            ra, rb, rd = rate(a, key), rate(b, key), rate(d, key)
            if not (ra <= rb <= rd):     # require monotonic: higher vol -> more pullbacks
                continue
            score = rd - ra
            table.append({"lo": lo, "hi": hi, "score": round(score, 2),
                          "n": [len(a), len(b), len(d)],
                          "rates": [round(ra, 2), round(rb, 2), round(rd, 2)]})
            if best is None or score > best["score"]:
                best = table[-1]
    table.sort(key=lambda x: -x["score"])
    return best, table[:10]


best_raw, top_raw = sweep(cases_raw)
best_scaled, top_scaled = sweep(cases_scaled)


def bucket_report(cases, lo, hi):
    out = {}
    for name, sub in (("vxn_lt%s" % lo, [c for c in cases if c["vxn"] < lo]),
                      ("vxn_%s_%s" % (lo, hi), [c for c in cases if lo <= c["vxn"] < hi]),
                      ("vxn_ge%s" % hi, [c for c in cases if c["vxn"] >= hi])):
        out[name] = {"n": len(sub),
                     **{"rate_%dd" % h: round(rate(sub, "hit_%d" % h), 2) for h in HORIZONS}}
    return out


report = {
    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "percentile_window": "%s ~ %s (n=%d)" % (common[0].date(), common[-1].date(), len(common)),
    "method_1_percentile_mapping": {
        "vix_16_is_pct": round(pct16, 2),
        "vix_20_is_pct": round(pct20, 2),
        "vxn_at_same_pct": {"lo": round(map_lo, 2), "hi": round(map_hi, 2)},
    },
    "method_2_spread": {
        "vxn_minus_vix": {"mean": round(float(spread.mean()), 2),
                          "median": round(float(spread.median()), 2),
                          "p10": round(float(spread.quantile(.10)), 2),
                          "p90": round(float(spread.quantile(.90)), 2)},
        "vxn_over_vix_ratio": {"mean": round(float(ratio.mean()), 3),
                               "median": round(float(ratio.median()), 3)},
        "rule_of_thumb_3to5_holds": bool(3 <= float(spread.median()) <= 5),
    },
    "volatility": {
        "ndx_daily_std_pct": round(float(nret.std()) * 100, 3),
        "spx_daily_std_pct": round(float(sret.std()) * 100, 3),
        "ndx_over_spx": round(vol_ratio, 3),
        "vol_scaled_pullback_pct": round(PULLBACK * vol_ratio * 100, 3),
    },
    "backtest_window": "%s ~ %s" % (cases_raw[0]["date"], cases_raw[-1]["date"]),
    "method_3_empirical": {
        "same_def_0.75pct": {"samples": len(cases_raw),
                             "base_rate_5d": round(rate(cases_raw, "hit_5"), 2),
                             "best": best_raw, "top10": top_raw},
        "vol_scaled": {"samples": len(cases_scaled),
                       "base_rate_5d": round(rate(cases_scaled, "hit_5"), 2),
                       "best": best_scaled, "top10": top_scaled},
    },
}

if best_scaled:
    report["buckets_at_best_scaled"] = bucket_report(cases_scaled, best_scaled["lo"], best_scaled["hi"])
if best_raw:
    report["buckets_at_best_raw"] = bucket_report(cases_raw, best_raw["lo"], best_raw["hi"])

with open(os.path.join(OUT_DIR, "calib_ndx.txt"), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print("OK: calib_ndx.txt written")
