import yfinance as yf
import json
import os
from datetime import datetime

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
result = {"checked_at": datetime.now().strftime("%Y-%m-%d %H:%M")}


def get_last_prev(ticker):
    """回傳 (last, prev)。先試 fast_info（即時），失敗用日線歷史備援。"""
    t = yf.Ticker(ticker)
    try:
        info = t.fast_info
        last = float(info["last_price"])
        prev = float(info["previous_close"])
        if last and prev:
            return last, prev
    except Exception:
        pass
    h = t.history(period="5d")
    if len(h) >= 2:
        return float(h["Close"].iloc[-1]), float(h["Close"].iloc[-2])
    return None, None


# ---- ES 標普期貨 ----
try:
    last, prev = get_last_prev("ES=F")
    chg = (last - prev) / prev * 100
    signal = "BULLISH" if chg >= 0.3 else "BEARISH" if chg <= -0.3 else "NEUTRAL"
    result["es"] = {"last": round(last, 2), "prev_close": round(prev, 2),
                    "change_pct": round(chg, 2), "signal": signal}
except Exception as e:
    result["es_error"] = str(e)

# ---- NQ 那斯達克期貨（科技強弱）----
try:
    nlast, nprev = get_last_prev("NQ=F")
    result["nq_change_pct"] = round((nlast - nprev) / nprev * 100, 2)
except Exception:
    pass

# ---- VIX 恐慌指數 ----
try:
    vlast, _ = get_last_prev("^VIX")
    result["vix"] = round(vlast, 2)
except Exception as e:
    result["vix_error"] = str(e)

# ---- 10Y 美債殖利率（^TNX，rate-driven 盤關鍵）----
try:
    ylast, yprev = get_last_prev("^TNX")
    # ^TNX 有時回傳 42.5 代表 4.25%，>20 視為需 /10 正規化
    if ylast > 20:
        ylast, yprev = ylast / 10, yprev / 10
    chg_bps = round((ylast - yprev) * 100, 1)
    ysig = "UP_RISK_OFF" if chg_bps >= 3 else "DOWN_RISK_ON" if chg_bps <= -3 else "FLAT"
    result["us10y"] = {"yield_pct": round(ylast, 3), "prev_pct": round(yprev, 3),
                       "change_bps": chg_bps, "signal": ysig}
except Exception as e:
    result["us10y_error"] = str(e)

# ---- DXY 美元指數（DX-Y.NYB）----
try:
    dlast, dprev = get_last_prev("DX-Y.NYB")
    dchg = (dlast - dprev) / dprev * 100
    dsig = "UP_RISK_OFF" if dchg >= 0.25 else "DOWN_RISK_ON" if dchg <= -0.25 else "FLAT"
    result["dxy"] = {"last": round(dlast, 2), "prev_close": round(dprev, 2),
                     "change_pct": round(dchg, 2), "signal": dsig}
except Exception as e:
    result["dxy_error"] = str(e)

# ---- 合成盤前總判讀（把 5 訊號變一句話）----
try:
    score = 0
    es_sig = result.get("es", {}).get("signal")
    if es_sig == "BULLISH":
        score += 1
    elif es_sig == "BEARISH":
        score -= 1
    nq = result.get("nq_change_pct")
    if nq is not None:
        score += 1 if nq >= 0.3 else -1 if nq <= -0.3 else 0
    y_sig = result.get("us10y", {}).get("signal")
    if y_sig == "UP_RISK_OFF":
        score -= 1
    elif y_sig == "DOWN_RISK_ON":
        score += 1
    d_sig = result.get("dxy", {}).get("signal")
    if d_sig == "UP_RISK_OFF":
        score -= 1
    elif d_sig == "DOWN_RISK_ON":
        score += 1
    vix = result.get("vix")
    if vix is not None:
        score += 1 if vix < 16 else -1 if vix > 20 else 0
    if score >= 2:
        backdrop = "RISK_ON 偏多"
    elif score <= -2:
        backdrop = "RISK_OFF 偏空"
    else:
        backdrop = "MIXED 中性"
    result["macro_backdrop"] = {"score": score, "read": backdrop,
                                "note": "ES+NQ+10Y+DXY+VIX 合成；±2 以上才定調，否則中性"}
except Exception as e:
    result["backdrop_error"] = str(e)

with open(os.path.join(OUT_DIR, "es_check.txt"), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
