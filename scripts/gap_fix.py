"""日線序列缺日偵測與回補。

2026-09-01 建立。起因：Yahoo 的日線後端把 2026-08-28（週五）整天漏掉，
^GSPC / SPY / ^VIX / QQQ 四個標的同時缺，但 30 分 K 後端的 8/28 完整存在（13 根）。
check_duplicate.py 只比對 trade_date，抓不到「序列中間缺一天」，
因此 MA / RSI / MACD / BB / KD / ATR / breadth 全部會靜默錯位一天，
prev_close 也會錯接到前一個交易日 —— 不報錯，但每個數字都是錯的。

判定依據：intraday（30m）與 daily 是 Yahoo 的兩個不同後端，不會同時漏同一天。
若某日在 30m 有資料而 daily 沒有，即認定 daily 缺日並回補。

冪等：Yahoo 修好後就偵測不到缺口，不會重複插入。
"""

import json
import os

import pandas as pd

import yf_compat

_DIR = os.path.dirname(os.path.abspath(__file__))
OVERRIDES = os.path.join(_DIR, "manual_ohlc_overrides.json")

# 30m 資料在 Yahoo 只保留約 60 天，且回補只對「近期」有意義（更早的缺口
# 影響的是 MA200 這種長窗，1 天誤差可忽略，不值得為它多打一次 API）。
LOOKBACK_DAYS = 45


def _load_overrides():
    try:
        with open(OVERRIDES, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _intraday_daily_bars(ticker):
    """用 30m K 聚合成日線 OHLCV。抓不到回傳空 dict，不阻斷主流程。"""
    try:
        raw = yf_compat.download(ticker, period="60d", interval="30m", progress=False)
        if raw is None or raw.empty:
            return {}
        if hasattr(raw.columns, "levels"):
            raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]
        raw = raw.dropna(subset=["Close"])
        out = {}
        for day, grp in raw.groupby(raw.index.strftime("%Y-%m-%d")):
            out[day] = {
                "Open": float(grp["Open"].iloc[0]),
                "High": float(grp["High"].max()),
                "Low": float(grp["Low"].min()),
                "Close": float(grp["Close"].iloc[-1]),
                "Volume": float(grp["Volume"].sum()),
                "_bars": len(grp),
            }
        return out
    except Exception:
        return {}


def patch_missing_days(df, ticker, log=None):
    """回補 df 中缺失的交易日。回傳 (df, patch_notes)。

    patch_notes 為 list，每筆記錄補了哪一天、資料來源、是否用了人工覆寫值。
    df 沒有缺日時回傳原 df 與空 list（最常見的情況，只多一次 30m API 呼叫）。
    """
    notes = []
    if df is None or df.empty:
        return df, notes

    have = set(df.index.strftime("%Y-%m-%d"))
    cutoff = (df.index.max() - pd.Timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    intra = _intraday_daily_bars(ticker)
    if not intra:
        return df, notes

    # 只補「在序列區間內」的缺日：早於 df 起點或晚於 df 終點的不算缺口
    lo = df.index.min().strftime("%Y-%m-%d")
    hi = df.index.max().strftime("%Y-%m-%d")
    missing = sorted(d for d in intra if lo < d < hi and d >= cutoff and d not in have)
    if not missing:
        return df, notes

    ov = _load_overrides().get(ticker, {})
    rows = {}
    for day in missing:
        bar = dict(intra[day])
        bars = bar.pop("_bars", 0)
        src = "30m aggregate (%d bars)" % bars
        used_ov = []
        for field, val in ov.get(day, {}).items():
            if field in bar:
                bar[field] = float(val)
                used_ov.append(field)
        if used_ov:
            src += " + manual override(%s)" % ",".join(sorted(used_ov))
        rows[pd.Timestamp(day)] = bar
        notes.append({"date": day, "ticker": ticker, "source": src,
                      "close": round(bar["Close"], 2)})
        if log:
            # ASCII only: CLAUDE.md 硬規則——不得 print 中文到 subprocess stdout（Windows cp950 亂碼）
            log("[gap_fix] %s missing %s -> backfilled (%s, close=%.2f)"
                % (ticker, day, src, bar["Close"]))

    add = pd.DataFrame.from_dict(rows, orient="index")
    add.index.name = df.index.name
    for col in df.columns:
        if col not in add.columns:
            add[col] = float("nan")
    out = pd.concat([df, add[list(df.columns)]]).sort_index()
    return out, notes
