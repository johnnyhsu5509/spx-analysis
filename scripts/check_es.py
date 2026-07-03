import yfinance as yf
import json
import os
from datetime import datetime

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
now = datetime.now()
result = {"checked_at": now.strftime("%Y-%m-%d %H:%M")}

# ---- 時段標示（台灣時間，美國夏令）----
# 亞洲盤=薄量易反轉，只供參考；US_PREOPEN/REGULAR 才是可執行讀數
h = now.hour
if 6 <= h < 15:
    session, s_note = "ASIA_THIN", "亞洲薄盤：流動性低、反轉率高，僅供參考，21:00後須複查再執行"
elif 15 <= h < 21:
    session, s_note = "EUROPE", "歐洲盤：中等可信度，開盤前再確認"
elif h == 21 and now.minute < 30:
    session, s_note = "US_PREOPEN", "美股開盤前：高可信度讀數"
elif (h >= 21) or (h < 4):
    session, s_note = "US_REGULAR", "美股盤中：即時讀數"
else:
    session, s_note = "US_AFTERHOURS", "美股盤後：反映當日收盤後動向"
result["session"] = {"label": session, "note": s_note}


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
    h2 = t.history(period="5d")
    if len(h2) >= 2:
        return float(h2["Close"].iloc[-1]), float(h2["Close"].iloc[-2])
    return None, None


# ---- ES 標普期貨 ----
es_pct = None
try:
    last, prev = get_last_prev("ES=F")
    es_pct = (last - prev) / prev * 100
    signal = "BULLISH" if es_pct >= 0.3 else "BEARISH" if es_pct <= -0.3 else "NEUTRAL"
    result["es"] = {"last": round(last, 2), "prev_close": round(prev, 2),
                    "change_pct": round(es_pct, 2), "signal": signal}
except Exception as e:
    result["es_error"] = str(e)

# ---- 隱含 SPX 開盤（用現貨前收 × ES 變動近似）----
try:
    with open(os.path.join(OUT_DIR, "today_data.txt"), encoding="utf-8") as f:
        spx_close = json.load(f)["close"]
    if es_pct is not None:
        result["implied_spx_open"] = {
            "approx": round(spx_close * (1 + es_pct / 100), 1),
            "spx_prev_close": spx_close,
            "note": "近似值(以ES%套現貨前收，未扣基差)"
        }
except Exception:
    pass

# ---- NQ 那斯達克期貨（科技領先）----
nq_pct = None
try:
    nlast, nprev = get_last_prev("NQ=F")
    nq_pct = round((nlast - nprev) / nprev * 100, 2)
    result["nq_change_pct"] = nq_pct
except Exception:
    pass

# ---- SOXX 半導體 ETF（rule15：類股溫度計，對重倉半導體者比NQ準）----
try:
    slast, sprev = get_last_prev("SOXX")
    soxx_pct = round((slast - sprev) / sprev * 100, 2)
    stale = session in ("ASIA_THIN", "EUROPE")
    entry = {"last": round(slast, 2), "change_pct": soxx_pct}
    if stale:
        entry["note"] = "ETF無夜盤，此為前一交易日資料（非即時）"
    result["soxx_semis"] = entry
    # 類股 vs 大盤背離（僅美盤時段有意義）
    if not stale and es_pct is not None:
        div = round(soxx_pct - es_pct, 2)
        result["semi_vs_spx"] = {
            "divergence_pp": div,
            "read": "半導體領跌(輪動殺半導體)" if div <= -1.0 else
                    "半導體領漲" if div >= 1.0 else "同步"
        }
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
    if ylast > 20:
        ylast, yprev = ylast / 10, yprev / 10
    chg_bps = round((ylast - yprev) * 100, 1)
    ysig = "UP_RISK_OFF" if chg_bps >= 3 else "DOWN_RISK_ON" if chg_bps <= -3 else "FLAT"
    result["us10y"] = {"yield_pct": round(ylast, 3), "prev_pct": round(yprev, 3),
                       "change_bps": chg_bps, "signal": ysig}
except Exception as e:
    result["us10y_error"] = str(e)

# ---- DXY 美元指數 ----
try:
    dlast, dprev = get_last_prev("DX-Y.NYB")
    dchg = (dlast - dprev) / dprev * 100
    dsig = "UP_RISK_OFF" if dchg >= 0.25 else "DOWN_RISK_ON" if dchg <= -0.25 else "FLAT"
    result["dxy"] = {"last": round(dlast, 2), "prev_close": round(dprev, 2),
                     "change_pct": round(dchg, 2), "signal": dsig}
except Exception as e:
    result["dxy_error"] = str(e)

# ---- 合成盤前總判讀 ----
try:
    score = 0
    es_sig = result.get("es", {}).get("signal")
    if es_sig == "BULLISH":
        score += 1
    elif es_sig == "BEARISH":
        score -= 1
    if nq_pct is not None:
        score += 1 if nq_pct >= 0.3 else -1 if nq_pct <= -0.3 else 0
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
    note = "ES+NQ+10Y+DXY+VIX 合成；±2 以上才定調"
    if session == "ASIA_THIN":
        note += "；亞洲薄盤讀數，可信度打折"
    result["macro_backdrop"] = {"score": score, "read": backdrop, "note": note}
except Exception as e:
    result["backdrop_error"] = str(e)

with open(os.path.join(OUT_DIR, "es_check.txt"), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
