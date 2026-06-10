import yfinance as yf
import json
import os
from datetime import datetime

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
result = {"checked_at": datetime.now().strftime("%Y-%m-%d %H:%M")}

try:
    es = yf.Ticker("ES=F")
    info = es.fast_info
    last = float(info["last_price"])
    prev = float(info["previous_close"])
    chg = (last - prev) / prev * 100
    if chg >= 0.3:
        signal = "BULLISH"
    elif chg <= -0.3:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"
    result["es"] = {
        "last": round(last, 2),
        "prev_close": round(prev, 2),
        "change_pct": round(chg, 2),
        "signal": signal
    }
except Exception as e:
    result["es_error"] = str(e)

try:
    vx = yf.Ticker("^VIX")
    result["vix"] = round(float(vx.fast_info["last_price"]), 2)
except Exception as e:
    result["vix_error"] = str(e)

try:
    nq = yf.Ticker("NQ=F")
    ninfo = nq.fast_info
    nlast = float(ninfo["last_price"])
    nprev = float(ninfo["previous_close"])
    result["nq_change_pct"] = round((nlast - nprev) / nprev * 100, 2)
except Exception:
    pass

with open(os.path.join(OUT_DIR, "es_check.txt"), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
