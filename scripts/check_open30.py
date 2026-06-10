import yfinance as yf
import json
import os
from datetime import datetime

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
result = {"checked_at": datetime.now().strftime("%Y-%m-%d %H:%M")}

try:
    raw = yf.download("^GSPC", period="2d", interval="30m", progress=False)
    if hasattr(raw.columns, 'levels'):
        raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]

    today = raw.index[-1].date()
    today_bars = raw[[i.date() == today for i in raw.index]]

    bars = []
    for ts, row in today_bars.iterrows():
        bars.append({
            "time": ts.strftime("%H:%M"),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"])
        })
    result["session_date"] = str(today)
    result["bars_30m"] = bars

    if bars:
        first = bars[0]
        last = bars[-1]
        day_open = first["open"]
        now_price = last["close"]
        result["open_price"] = day_open
        result["current_price"] = now_price
        result["change_from_open_pct"] = round((now_price - day_open) / day_open * 100, 2)
        result["first_30m_direction"] = "UP" if first["close"] > first["open"] else "DOWN" if first["close"] < first["open"] else "FLAT"
        result["first_30m_range"] = {"high": first["high"], "low": first["low"]}
        result["first_30m_volume"] = first["volume"]
except Exception as e:
    result["error"] = str(e)

try:
    vx = yf.Ticker("^VIX")
    result["vix"] = round(float(vx.fast_info["last_price"]), 2)
except Exception:
    pass

with open(os.path.join(OUT_DIR, "open30_check.txt"), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
