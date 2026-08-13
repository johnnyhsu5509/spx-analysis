import yfinance as yf
import sys
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import yf_compat
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
    t = yf_compat.ticker(ticker)
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

# ---- 隱含 SPX 開盤（方案A：ES點數錨定法，基差自動抵銷，免疫季度換倉）----
try:
    with open(os.path.join(OUT_DIR, "today_data.txt"), encoding="utf-8") as f:
        td = json.load(f)
    spx_close = td["close"]
    spx_date = td["trade_date"]
    est = None
    try:
        import pandas as pd
        es_intra = yf_compat.history("ES=F", period="5d", interval="15m", prepost=True).dropna(subset=["Close"])
        if len(es_intra):
            anchor_ts = pd.Timestamp(spx_date).tz_localize("America/New_York") + pd.Timedelta(hours=16)
            diffs = abs(es_intra.index - anchor_ts)
            pos = int(diffs.argmin())
            if diffs[pos] <= pd.Timedelta(hours=2):
                es_anchor = float(es_intra["Close"].iloc[pos])
                es_now = float(es_intra["Close"].iloc[-1])
                pt_chg = es_now - es_anchor
                est = {
                    "approx": round(spx_close + pt_chg, 1),
                    "spx_prev_close": spx_close,
                    "es_at_prior_close": round(es_anchor, 2),
                    "es_pt_chg": round(pt_chg, 2),
                    "method": "point_anchor",
                    "note": "方案A：ES點數錨定，基差已抵銷"
                }
    except Exception:
        pass
    if est is None and es_pct is not None:   # fallback：退回舊百分比法並標記
        est = {
            "approx": round(spx_close * (1 + es_pct / 100), 1),
            "spx_prev_close": spx_close,
            "method": "pct_fallback_degraded",
            "note": "近似值(以ES%套現貨前收，未扣基差)——錨點抓取失敗時的降級模式"
        }
    if est is not None:
        result["implied_spx_open"] = est
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

# --- 資料完整性把關（避免全數抓取失敗仍寫出「中性」假訊號）---
_err_keys = [k for k in result if k.endswith("_error")]
_have_es = "es" in result and isinstance(result.get("es"), dict)
_have_vix = result.get("vix") is not None
_have_10y = "us10y" in result and isinstance(result.get("us10y"), dict)
_core_ok = sum([_have_es, _have_vix, _have_10y])

if _core_ok == 0:
    result["data_status"] = "ALL_FAILED"
    result.pop("macro_backdrop", None)   # 全掛時不得留下 score 0 = 中性的誤導
elif _err_keys:
    result["data_status"] = "PARTIAL(%d core ok, errors: %s)" % (_core_ok, ",".join(_err_keys))
    if "macro_backdrop" in result:
        result["macro_backdrop"]["note"] = ("[PARTIAL DATA - 部分指標缺失,合成分不可信] "
                                            + result["macro_backdrop"].get("note", ""))
else:
    result["data_status"] = "OK"

with open(os.path.join(OUT_DIR, "es_check.txt"), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

if _core_ok == 0:
    snap = os.path.join(os.path.dirname(OUT_DIR), "data", "es_check.txt")
    try:
        with open(snap, encoding="utf-8") as f:
            sd = json.load(f)
        if sd.get("es") or sd.get("vix") is not None:
            sd["data_status"] = "SNAPSHOT(from data/, original checked_at=%s)" % sd.get("checked_at", "?")
            sd["snapshot_note"] = "live fetch all failed; this is the Actions morning snapshot - STALE for futures/open checks"
            with open(os.path.join(OUT_DIR, "es_check.txt"), "w", encoding="utf-8") as f:
                json.dump(sd, f, ensure_ascii=False, indent=2)
            print("OK data_status=SNAPSHOT (stale; usable for daily analysis only)")
            sys.exit(0)
    except Exception:
        pass
    print("CHECK_ES FAILED: no core data (ES/VIX/10Y all failed). errors=%s" % ",".join(_err_keys))
    print("es_check.txt written with data_status=ALL_FAILED (no macro_backdrop).")
    sys.exit(1)
print("OK data_status=%s" % result["data_status"])
