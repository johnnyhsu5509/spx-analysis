import yfinance as yf
import sys
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import yf_compat
import guard
import json
import os
from datetime import datetime

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# 標的設定。SPX 為預設（行為與參數化前相同）；NDX 為 2026-08-18 新增。
# 主/次期貨在兩套之間對調：SPX 看 ES 為主、NQ 為輔；NDX 反過來。
# 波動門檻 SPX 用 VIX 16/20、NDX 用 VXN 18/28（校準值，非沿用）。
# ---------------------------------------------------------------------------
SYMBOLS = {
    "spx": {
        "label": "SPX",
        "fut": ("ES=F", "es"), "fut2": ("NQ=F", "nq_change_pct"),
        "vol": ("^VIX", "vix", 16, 20),
        "data_file": "today_data.txt", "outfile": "es_check.txt",
        "implied_key": "implied_spx_open", "semi_key": "semi_vs_spx",
    },
    "ndx": {
        "label": "NDX",
        "fut": ("NQ=F", "nq"), "fut2": ("ES=F", "es_change_pct"),
        "vol": ("^VXN", "vxn", 18, 28),
        "data_file": "ndx_today_data.txt", "outfile": "ndx_es_check.txt",
        "implied_key": "implied_ndx_open", "semi_key": "semi_vs_ndx",
    },
}

_argv = sys.argv[1:]
SYM = "spx"
for i, a in enumerate(_argv):
    if a == "--symbol" and i + 1 < len(_argv):
        SYM = _argv[i + 1].strip().lower()
    elif a.startswith("--symbol="):
        SYM = a.split("=", 1)[1].strip().lower()
if SYM not in SYMBOLS:
    print("UNKNOWN SYMBOL: %s (expected one of: %s)" % (SYM, ", ".join(sorted(SYMBOLS))))
    sys.exit(2)
CFG = SYMBOLS[SYM]
FUT, FUT_KEY = CFG["fut"]
FUT2, FUT2_KEY = CFG["fut2"]
VOL_TICK, VOL_KEY, VOL_LO, VOL_HI = CFG["vol"]
OUTFILE = CFG["outfile"]

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


# ---- 主期貨（SPX:ES / NDX:NQ）----
es_pct = None
try:
    last, prev = get_last_prev(FUT)
    es_pct = (last - prev) / prev * 100
    signal = "BULLISH" if es_pct >= 0.3 else "BEARISH" if es_pct <= -0.3 else "NEUTRAL"
    result[FUT_KEY] = {"last": round(last, 2), "prev_close": round(prev, 2),
                       "change_pct": round(es_pct, 2), "signal": signal}
except Exception as e:
    result["%s_error" % FUT_KEY] = str(e)

# ---- 隱含開盤（方案A：期貨點數錨定法，基差自動抵銷，免疫季度換倉）----
# 讀資料檔前先驗證來源：拿到另一套的收盤價會算出完全錯誤的隱含開盤
guard.require_symbol(os.path.join(OUT_DIR, CFG["data_file"]), CFG["label"],
                     "implied-open source")
try:
    with open(os.path.join(OUT_DIR, CFG["data_file"]), encoding="utf-8") as f:
        td = json.load(f)
    spx_close = td["close"]
    spx_date = td["trade_date"]
    est = None
    try:
        import pandas as pd
        es_intra = yf_compat.history(FUT, period="5d", interval="15m", prepost=True).dropna(subset=["Close"])
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
                    "index_prev_close": spx_close,
                    "fut_at_prior_close": round(es_anchor, 2),
                    "fut_pt_chg": round(pt_chg, 2),
                    "method": "point_anchor",
                    "note": "方案A：%s點數錨定，基差已抵銷" % FUT
                }
    except Exception:
        pass
    if est is None and es_pct is not None:   # fallback：退回舊百分比法並標記
        est = {
            "approx": round(spx_close * (1 + es_pct / 100), 1),
            "index_prev_close": spx_close,
            "method": "pct_fallback_degraded",
            "note": "近似值(以%s%%套現貨前收，未扣基差)——錨點抓取失敗時的降級模式" % FUT
        }
    if est is not None:
        if SYM == "spx":   # 保留原欄位名，避免既有 SKILL 解析失效
            est["spx_prev_close"] = est.pop("index_prev_close")
            if "fut_at_prior_close" in est:
                est["es_at_prior_close"] = est.pop("fut_at_prior_close")
                est["es_pt_chg"] = est.pop("fut_pt_chg")
            est["note"] = est["note"].replace("ES=F", "ES")
        result[CFG["implied_key"]] = est
except Exception:
    pass

# ---- 次期貨（SPX:NQ 科技領先 / NDX:ES 大盤對照）----
nq_pct = None
try:
    nlast, nprev = get_last_prev(FUT2)
    nq_pct = round((nlast - nprev) / nprev * 100, 2)
    result[FUT2_KEY] = nq_pct
except Exception:
    pass

# ---- SOXX 半導體 ETF（rule15：類股溫度計；對 NDX 權重更高）----
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
        result[CFG["semi_key"]] = {
            "divergence_pp": div,
            "read": "半導體領跌(輪動殺半導體)" if div <= -1.0 else
                    "半導體領漲" if div >= 1.0 else "同步"
        }
except Exception:
    pass

# ---- 波動指數（SPX:VIX / NDX:VXN）----
try:
    vlast, _ = get_last_prev(VOL_TICK)
    result[VOL_KEY] = round(vlast, 2)
except Exception as e:
    result["%s_error" % VOL_KEY] = str(e)

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
    es_sig = result.get(FUT_KEY, {}).get("signal")
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
    vix = result.get(VOL_KEY)
    if vix is not None:
        score += 1 if vix < VOL_LO else -1 if vix > VOL_HI else 0
    if score >= 2:
        backdrop = "RISK_ON 偏多"
    elif score <= -2:
        backdrop = "RISK_OFF 偏空"
    else:
        backdrop = "MIXED 中性"
    note = "%s+%s+10Y+DXY+%s 合成；±2 以上才定調" % (
        FUT.replace("=F", ""), FUT2.replace("=F", ""), VOL_KEY.upper())
    if session == "ASIA_THIN":
        note += "；亞洲薄盤讀數，可信度打折"
    result["macro_backdrop"] = {"score": score, "read": backdrop, "note": note}
except Exception as e:
    result["backdrop_error"] = str(e)

# --- 資料完整性把關（避免全數抓取失敗仍寫出「中性」假訊號）---
_err_keys = [k for k in result if k.endswith("_error")]
_have_es = FUT_KEY in result and isinstance(result.get(FUT_KEY), dict)
_have_vix = result.get(VOL_KEY) is not None
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

with open(os.path.join(OUT_DIR, OUTFILE), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

if _core_ok == 0:
    snap = os.path.join(os.path.dirname(OUT_DIR), "data", OUTFILE)
    try:
        with open(snap, encoding="utf-8") as f:
            sd = json.load(f)
        if sd.get(FUT_KEY) or sd.get(VOL_KEY) is not None:
            sd["data_status"] = "SNAPSHOT(from data/, original checked_at=%s)" % sd.get("checked_at", "?")
            sd["snapshot_note"] = "live fetch all failed; this is the Actions morning snapshot - STALE for futures/open checks"
            with open(os.path.join(OUT_DIR, OUTFILE), "w", encoding="utf-8") as f:
                json.dump(sd, f, ensure_ascii=False, indent=2)
            print("OK data_status=SNAPSHOT (stale; usable for daily analysis only)")
            sys.exit(0)
    except Exception:
        pass
    print("CHECK_ES FAILED: no core data (%s/%s/10Y all failed). errors=%s"
          % (FUT_KEY.upper(), VOL_KEY.upper(), ",".join(_err_keys)))
    print("%s written with data_status=ALL_FAILED (no macro_backdrop)." % OUTFILE)
    sys.exit(1)
print("OK data_status=%s" % result["data_status"])
