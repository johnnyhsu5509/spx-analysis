"""rule43 量能門檻校準（每季重跑一次）

「帶量」改用百分位定義而非固定倍數。原因：固定 1.1 倍在不同標的上代表
的嚴格度不同（^NDX 是 P78、QQQ 只有 P69），rule36 強制換代理時會讓門檻
悄悄放寬約 9 個百分點，違反 rule33 口徑一致性。

用法：python3 calib_volume.py
輸出：vol_threshold.json（供 SKILL 引用的當期門檻值）
"""
import json
import numpy as np
import pandas as pd
import yfinance as yf

PCTL = 75          # 帶量定義＝該序列自身分布的 P75（前四分之一）
LOOKBACK = "750d"  # 約三年
TICKERS = [("QQQ", "QQQ"), ("NDX", "^NDX"), ("SPY", "SPY"), ("SPX", "^GSPC")]


def rel_volume(ticker):
    d = yf.download(ticker, period=LOOKBACK, progress=False, auto_adjust=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    v = d.dropna(subset=["Close"])["Volume"].astype(float)
    return (v / v.shift(1).rolling(20).mean()).dropna()


out = {"pctl": PCTL, "lookback": LOOKBACK}
for name, ticker in TICKERS:
    r = rel_volume(ticker).iloc[:-1]  # 排除最新未結算列
    out[name] = {
        "n": int(len(r)),
        "median": round(float(r.median()), 3),
        "threshold": round(float(np.percentile(r, PCTL)), 3),
        "pctl_of_1_1": round(float((r < 1.1).mean() * 100), 1),
        "pass_rate_pct": round(float((r >= np.percentile(r, PCTL)).mean() * 100), 1),
    }

with open("vol_threshold.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print("OK")
