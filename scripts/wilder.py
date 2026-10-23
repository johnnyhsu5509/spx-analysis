"""Wilder RSI 與 Cutler／Wilder 背離旗標（rules_todo todo3）。

fetch_today.py 的 `rsi` 欄位維持 Cutler（簡單 14 日均），本模組只供附加的新欄位使用。
"""
import pandas as pd


def rsi(close, n=14):
    """Wilder 平滑：首值為前 n 個漲跌的簡單平均，其後 avg = (avg×(n−1) + x) / n。資料不足回傳全 NaN。"""
    d = close.diff().dropna()
    if len(d) < n:
        return pd.Series(float("nan"), index=close.index)

    def smooth(x):
        seed = pd.Series([x.iloc[:n].mean()], index=x.index[n - 1:n])
        return pd.concat([seed, x.iloc[n:]]).ewm(alpha=1 / n, adjust=False).mean()

    return 100 - 100 / (1 + smooth(d.clip(lower=0)) / smooth(-d.clip(upper=0)))


def divergence(cutler, wilder):
    """兩種 RSI 當日變動方向相反 → flag=True。任一缺值回傳 None，不得讀成「無背離」。"""
    c = round(float(cutler.iloc[-1] - cutler.iloc[-2]), 2)
    w = round(float(wilder.iloc[-1] - wilder.iloc[-2]), 2)
    if c != c or w != w:
        return None
    out = {"flag": c * w < 0, "cutler_chg": c, "wilder_chg": w}
    if out["flag"]:
        out["note"] = "Cutler 與 Wilder RSI 當日變動方向相反：Cutler 可能受 14 日窗口滑出的大幅變動扭曲"
    return out
