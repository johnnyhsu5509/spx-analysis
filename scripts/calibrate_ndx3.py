# -*- coding: utf-8 -*-
"""Stability / walk-forward pass for the VXN cut calibration.

Companion to calibrate_ndx.py (which does percentile mapping + spread stats).
This one answers the question that decided the final cuts: is a candidate cut
robust, or is it just fitting one calendar episode?

Each case carries its own date so the per-year table is trustworthy (an earlier
draft paired cases with the raw index and mislabelled every row by ~200 trading
days). Adds a walk-forward check: pick cuts on the early window, score them on
the later one.

This is what rejected the optimizer's best cut (16/32): 78% of its low-vol
bucket sits in 2016-2017 and it fires zero times in 2021/22/25/26. Final cuts
18/28 are recorded in docs/ndx_regime_baseline.json via backtest_ndx.py.

ASCII-only stdout. Results -> calib_ndx3.txt
"""
import json
import os
from datetime import datetime

import yf_compat

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
HORIZONS = [1, 3, 5]


def flat(df):
    if df is not None and hasattr(df.columns, "levels"):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def dl(sym, start):
    df = flat(yf_compat.download(sym, start=start, progress=False))
    if df is None or df.empty:
        raise SystemExit("FETCH FAILED: " + sym)
    return df


# longer window so the low-vol regime is represented, not just 2021-2026
BT_START = "2015-01-01"
ndx = dl("^NDX", BT_START)
spx = dl("^GSPC", BT_START)
vxn = dl("^VXN", BT_START)["Close"].squeeze()

nclose, nlow = ndx["Close"].squeeze(), ndx["Low"].squeeze()
ma20, ma200 = nclose.rolling(20).mean(), nclose.rolling(200).mean()
vxn_b = vxn.reindex(nclose.index).ffill()

vol_ratio = float(nclose.pct_change().dropna().std() / spx["Close"].squeeze().pct_change().dropna().std())
PULLBACK = 0.0075 * vol_ratio

cases = []
maxH = max(HORIZONS)
for i in range(len(nclose)):
    c, m20, m200, v = nclose.iloc[i], ma20.iloc[i], ma200.iloc[i], vxn_b.iloc[i]
    if any(x != x for x in (m20, m200, v)) or i + maxH >= len(nclose):
        continue
    row = {"date": str(nclose.index[i].date()), "year": nclose.index[i].year, "vxn": float(v)}
    for h in HORIZONS:
        row["hit_%d" % h] = 1 if nlow.iloc[i + 1:i + 1 + h].min() <= c * (1 - PULLBACK) else 0
    cases.append(row)

N = len(cases)


def rate(sub, key="hit_5"):
    return sum(c[key] for c in sub) / len(sub) * 100 if sub else float("nan")


def split3(cs, lo, hi):
    return ([c for c in cs if c["vxn"] < lo],
            [c for c in cs if lo <= c["vxn"] < hi],
            [c for c in cs if c["vxn"] >= hi])


def sweep(cs, floor_frac=0.10):
    n = len(cs)
    table = []
    for lo10 in range(130, 285, 5):
        for hi10 in range(200, 385, 5):
            lo, hi = lo10 / 10.0, hi10 / 10.0
            if hi <= lo + 2.0:
                continue
            a, b, d = split3(cs, lo, hi)
            if min(len(a), len(b), len(d)) < n * floor_frac:
                continue
            ra, rb, rd = rate(a), rate(b), rate(d)
            if not (ra <= rb <= rd):
                continue
            table.append({"lo": lo, "hi": hi, "score": round(rd - ra, 2),
                          "n": [len(a), len(b), len(d)],
                          "rates": [round(ra, 2), round(rb, 2), round(rd, 2)]})
    table.sort(key=lambda x: -x["score"])
    return table


full = sweep(cases)

# ---- walk-forward: choose on first half, score on second half ----
train = [c for c in cases if c["year"] <= 2021]
test = [c for c in cases if c["year"] >= 2022]
tr_sweep = sweep(train)
wf = None
if tr_sweep:
    lo, hi = tr_sweep[0]["lo"], tr_sweep[0]["hi"]
    a, b, d = split3(test, lo, hi)
    wf = {"chosen_on_train": {"lo": lo, "hi": hi, "train_rates": tr_sweep[0]["rates"],
                              "train_n": tr_sweep[0]["n"]},
          "test_n": [len(a), len(b), len(d)],
          "test_rates": [round(rate(a), 2), round(rate(b), 2), round(rate(d), 2)],
          "test_monotonic": rate(a) <= rate(b) <= rate(d),
          "test_score": round(rate(d) - rate(a), 2)}


def yearly_at(lo, hi):
    out = {}
    for c in cases:
        b = "low" if c["vxn"] < lo else ("mid" if c["vxn"] < hi else "high")
        out.setdefault(str(c["year"]), {}).setdefault(b, []).append(c["hit_5"])
    return {y: {b: {"n": len(v), "rate": round(sum(v) / len(v) * 100, 1)}
                for b, v in sorted(bs.items())} for y, bs in sorted(out.items())}


report = {
    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "window": "%s ~ %s" % (cases[0]["date"], cases[-1]["date"]),
    "samples": N,
    "vol_ratio_ndx_over_spx": round(vol_ratio, 3),
    "pullback_used_pct": round(PULLBACK * 100, 3),
    "base_rate_5d": round(rate(cases), 2),
    "best_full": full[0] if full else None,
    "top8_full": full[:8],
    "walk_forward": wf,
}
if full:
    report["yearly_at_best"] = yearly_at(full[0]["lo"], full[0]["hi"])
# also show the round-number candidate for comparison
report["yearly_at_round_18_28"] = yearly_at(18.0, 28.0)
a, b, d = split3(cases, 18.0, 28.0)
report["round_18_28"] = {"n": [len(a), len(b), len(d)],
                         "rates": [round(rate(a), 2), round(rate(b), 2), round(rate(d), 2)],
                         "rates_1d": [round(rate(a, "hit_1"), 2), round(rate(b, "hit_1"), 2), round(rate(d, "hit_1"), 2)],
                         "rates_3d": [round(rate(a, "hit_3"), 2), round(rate(b, "hit_3"), 2), round(rate(d, "hit_3"), 2)]}

with open(os.path.join(OUT_DIR, "calib_ndx3.txt"), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print("OK: calib_ndx3.txt written")
