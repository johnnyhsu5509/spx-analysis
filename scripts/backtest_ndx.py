# -*- coding: utf-8 -*-
"""NDX regime baseline -- the NDX counterpart of backtest.py.

Differences from the SPX version, and why:

  index      ^NDX     (was ^GSPC)
  vol        ^VXN     (was ^VIX)
  vol cuts   18 / 28  (was 16 / 20)   -- calibrated, see calibrate_ndx*.py.
             The optimizer's best cut (16/32) was rejected: 78% of its low-vol
             bucket sits in 2016-2017 and it fires zero times in 2021/22/25/26.
             18/28 scores slightly worse but actually occurs in live markets.
  pullback   1.00%    (was 0.75%)     -- NDX daily sigma is 1.25-1.37x SPX, so
             the same -0.75% trigger is a materially more common event on NDX
             and the two systems' probabilities would not be comparable.

Runs two windows: 2015+ (primary, stable, spans a low-vol regime) and 2021+
(matches SPX backtest.py so the two systems' base rates line up).

ASCII-only stdout. Writes docs/ndx_regime_baseline.json + backtest_ndx_result.txt
"""
import json
import os
from datetime import datetime

import yf_compat

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(OUT_DIR)

PULLBACK = 0.0100
HORIZONS = [1, 3, 5]
VXN_LO, VXN_HI = 18.0, 28.0
WINDOWS = {"primary_2015": "2015-01-01", "spx_matched_2021": "2021-01-01"}


def flat(df):
    if df is not None and hasattr(df.columns, "levels"):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def dl(sym, start):
    df = flat(yf_compat.download(sym, start=start, progress=False))
    if df is None or df.empty:
        raise SystemExit("FETCH FAILED: " + sym)
    return df


def vxn_bucket(v):
    if v < VXN_LO:
        return "vxn_lt18"
    if v < VXN_HI:
        return "vxn_18_28"
    return "vxn_ge28"


def auc(scores, labels):
    pairs = sorted(zip(scores, range(len(scores))), key=lambda x: x[0])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[pairs[k][1]] = avg
        i = j + 1
    pos = [ranks[k] for k in range(len(labels)) if labels[k] == 1]
    npos, nneg = len(pos), len(labels) - len(pos)
    if npos == 0 or nneg == 0:
        return float("nan")
    return (sum(pos) - npos * (npos + 1) / 2) / (npos * nneg)


def run(start):
    ndx = dl("^NDX", start)
    spx = dl("^GSPC", start)
    vxn = dl("^VXN", start)["Close"].squeeze()

    close, low = ndx["Close"].squeeze(), ndx["Low"].squeeze()
    ma20, ma200 = close.rolling(20).mean(), close.rolling(200).mean()
    v_s = vxn.reindex(close.index).ffill()

    vol_ratio = float(close.pct_change().dropna().std()
                      / spx["Close"].squeeze().pct_change().dropna().std())

    n, maxH = len(close), max(HORIZONS)
    cases = []
    for i in range(n):
        c, m20, m200, v = close.iloc[i], ma20.iloc[i], ma200.iloc[i], v_s.iloc[i]
        if any(x != x for x in (m20, m200, v)) or i + maxH >= n:
            continue
        ext = (c - m20) / m20 * 100
        row = {
            "date": str(close.index[i].date()),
            "vxn": vxn_bucket(v),
            "trend": "above_ma200" if c >= m200 else "below_ma200",
            "ext": "ma20_over3" if ext >= 3 else ("ma20_under3" if ext <= -3 else "ma20_normal"),
        }
        for h in HORIZONS:
            row["hit_%d" % h] = 1 if low.iloc[i + 1:i + 1 + h].min() <= c * (1 - PULLBACK) else 0
        cases.append(row)

    N = len(cases)

    def rate(sub, key):
        return sum(c[key] for c in sub) / len(sub) * 100 if sub else float("nan")

    def bucket_rates(dim, key):
        return {b: {"n": len([c for c in cases if c[dim] == b]),
                    "rate": round(rate([c for c in cases if c[dim] == b], key), 2)}
                for b in sorted(set(c[dim] for c in cases))}

    rates_5d = {d: bucket_rates(d, "hit_5") for d in ("vxn", "trend", "ext")}
    for c in cases:
        c["pred"] = (rates_5d["vxn"][c["vxn"]]["rate"]
                     + rates_5d["trend"][c["trend"]]["rate"]
                     + rates_5d["ext"][c["ext"]]["rate"]) / 3

    preds = [c["pred"] for c in cases]
    metrics = {}
    for h in HORIZONS:
        labels = [c["hit_%d" % h] for c in cases]
        metrics["%dd" % h] = {
            "auc": round(auc(preds, labels), 3),
            "brier": round(sum((c["pred"] / 100 - c["hit_%d" % h]) ** 2 for c in cases) / N, 4),
        }

    # per-year low-bucket counts: exposes whether a bucket has gone extinct
    yearly_vxn = {}
    for c in cases:
        yearly_vxn.setdefault(c["date"][:4], {}).setdefault(c["vxn"], 0)
        yearly_vxn[c["date"][:4]][c["vxn"]] += 1

    return {
        "date_range": "%s ~ %s" % (cases[0]["date"], cases[-1]["date"]),
        "samples": N,
        "vol_ratio_ndx_over_spx": round(vol_ratio, 3),
        "base_rate": {"%dd" % h: round(rate(cases, "hit_%d" % h), 2) for h in HORIZONS},
        "model_metrics_vs_horizon": metrics,
        "regime_5d_rates": rates_5d,
        "vxn_bucket_by_year": yearly_vxn,
    }


results = {k: run(v) for k, v in WINDOWS.items()}
prim = results["primary_2015"]

report = {
    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "index": "^NDX", "vol_index": "^VXN", "futures": "NQ=F",
    "pullback_def": "future N-day intraday low <= signal close -1.00pct",
    "pullback_note": "1.00pct not 0.75pct: NDX daily sigma is 1.25-1.37x SPX; "
                     "same-percentage trigger would not be comparable across systems",
    "vxn_cuts": {"lo": VXN_LO, "hi": VXN_HI,
                 "why": "calibrated; optimizer best (16/32) rejected as overfit "
                        "(78pct of its low bucket in 2016-2017, zero fires 2021/22/25/26)"},
    "windows": results,
    "fetch_today_constants": {
        "BASE_5D": prim["base_rate"]["5d"],
        "vxn": {k: v["rate"] for k, v in prim["regime_5d_rates"]["vxn"].items()},
        "trend": {k: v["rate"] for k, v in prim["regime_5d_rates"]["trend"].items()},
        "ext": {k: v["rate"] for k, v in prim["regime_5d_rates"]["ext"].items()},
    },
    "known_limitation": "VXN rarely drops below 18 in the current regime "
                        "(2025 n=16, 2026 n=0). The risk-on bucket is近乎 dormant; "
                        "treat mid-bucket as the practical baseline until VXN mean-reverts.",
}

with open(os.path.join(OUT_DIR, "backtest_ndx_result.txt"), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
with open(os.path.join(REPO, "docs", "ndx_regime_baseline.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print("OK: ndx_regime_baseline.json written")
