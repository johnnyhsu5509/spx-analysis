import yfinance as yf
import json
import os
from datetime import datetime

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(OUT_DIR)

# 拉回定義（與 Codex 對齊，供雙系統可比）：未來 N 日盤中低點 <= 訊號日收盤 -0.75%
PULLBACK = 0.0075
HORIZONS = [1, 3, 5]
START = "2021-01-01"   # 下載起點，留 200 根給 MA200，實際評分約從 2021Q4 起

raw_spx = yf.download("^GSPC", start=START, progress=False)
raw_vix = yf.download("^VIX", start=START, progress=False)
for r in (raw_spx, raw_vix):
    if hasattr(r.columns, "levels"):
        r.columns = [c[0] if isinstance(c, tuple) else c for c in r.columns]

close = raw_spx["Close"].squeeze()
low = raw_spx["Low"].squeeze()
ma20 = close.rolling(20).mean()
ma200 = close.rolling(200).mean()
vix = raw_vix["Close"].squeeze().reindex(close.index).ffill()

n = len(close)
maxH = max(HORIZONS)


def vix_bucket(v):
    if v < 16:
        return "vix_lt16"
    if v < 20:
        return "vix_16_20"
    return "vix_ge20"


def trend_bucket(c, m200):
    return "above_ma200" if c >= m200 else "below_ma200"


def ext_bucket(c, m20):
    e = (c - m20) / m20 * 100
    if e >= 3:
        return "ma20_over3"
    if e <= -3:
        return "ma20_under3"
    return "ma20_normal"


# 建立每個訊號日的 regime 標籤 + 各時間框架 outcome（嚴格防偷看）
cases = []
for i in range(n):
    c = close.iloc[i]
    m20, m200, v = ma20.iloc[i], ma200.iloc[i], vix.iloc[i]
    if any(x != x for x in (m20, m200, v)):  # NaN 跳過（MA 未滿）
        continue
    if i + maxH >= n:  # 未來不足，無法判 outcome
        continue
    row = {
        "date": str(close.index[i].date()),
        "vix": vix_bucket(v),
        "trend": trend_bucket(c, m200),
        "ext": ext_bucket(c, m20),
    }
    for h in HORIZONS:
        fut_low = low.iloc[i + 1:i + 1 + h].min()
        row[f"hit_{h}"] = 1 if fut_low <= c * (1 - PULLBACK) else 0
    cases.append(row)

N = len(cases)


def rate(subset, key):
    s = [c[key] for c in subset]
    return sum(s) / len(s) * 100 if s else float("nan")


def bucket_rates(dim, key):
    out = {}
    for b in sorted(set(c[dim] for c in cases)):
        sub = [c for c in cases if c[dim] == b]
        out[b] = {"n": len(sub), "rate": round(rate(sub, key), 2)}
    return out


def auc(scores, labels):
    # Mann-Whitney U / rank-based AUC，含 tie 平均秩
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


# 用 5D 各 bucket 拉回率，組出每日「regime 平均機率」當預測分數
rates_5d = {
    "vix": bucket_rates("vix", "hit_5"),
    "trend": bucket_rates("trend", "hit_5"),
    "ext": bucket_rates("ext", "hit_5"),
}
for c in cases:
    p = (rates_5d["vix"][c["vix"]]["rate"]
         + rates_5d["trend"][c["trend"]]["rate"]
         + rates_5d["ext"][c["ext"]]["rate"]) / 3
    c["pred"] = p

report = {
    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "date_range": f"{cases[0]['date']} ~ {cases[-1]['date']}",
    "samples": N,
    "pullback_def": "未來N日盤中低點 <= 訊號日收盤 -0.75%",
    "base_rate": {f"{h}d": round(rate(cases, f"hit_{h}"), 2) for h in HORIZONS},
    "model_metrics_vs_horizon": {},
    "regime_5d_rates": rates_5d,
}

preds = [c["pred"] for c in cases]
for h in HORIZONS:
    labels = [c[f"hit_{h}"] for c in cases]
    a = auc(preds, labels)
    brier = sum((c["pred"] / 100 - c[f"hit_{h}"]) ** 2 for c in cases) / N
    report["model_metrics_vs_horizon"][f"{h}d"] = {
        "auc": round(a, 3),
        "brier": round(brier, 4),
    }

# 更新給 fetch_today.py 用的常數（5D，附超額）
base5 = report["base_rate"]["5d"]
report["fetch_today_constants"] = {
    "BASE_5D": base5,
    "vix": {k: v["rate"] for k, v in rates_5d["vix"].items()},
    "trend": {k: v["rate"] for k, v in rates_5d["trend"].items()},
    "ext": {k: v["rate"] for k, v in rates_5d["ext"].items()},
}

# 可讀報告（gitignore，供 Read 檢視）
with open(os.path.join(OUT_DIR, "backtest_result.txt"), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

# 持久基準（tracked，供 SKILL 引用、跨電腦同步、解決漂移）
with open(os.path.join(REPO, "docs", "regime_baseline.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
