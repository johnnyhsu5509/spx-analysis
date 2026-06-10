import yfinance as yf
import json
import os
from datetime import datetime, timedelta

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

end = datetime.today() + timedelta(days=1)
start = end - timedelta(days=300)

raw_spx = yf.download("^GSPC", start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), progress=False)
raw_vix = yf.download("^VIX", start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), progress=False)

if hasattr(raw_spx.columns, 'levels'):
    raw_spx.columns = [c[0] if isinstance(c, tuple) else c for c in raw_spx.columns]
if hasattr(raw_vix.columns, 'levels'):
    raw_vix.columns = [c[0] if isinstance(c, tuple) else c for c in raw_vix.columns]

spx_close = raw_spx["Close"].squeeze()
spx_open = raw_spx["Open"].squeeze()
spx_high = raw_spx["High"].squeeze()
spx_low = raw_spx["Low"].squeeze()
spx_vol = raw_spx["Volume"].squeeze()

result = {}

if not spx_close.empty:
    close = float(spx_close.iloc[-1])
    prev_close = float(spx_close.iloc[-2])
    change_pct = (close - prev_close) / prev_close * 100

    def sma(n):
        return float(spx_close.rolling(n).mean().iloc[-1])

    delta = spx_close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = float(100 - 100 / (1 + (gain / loss).iloc[-1]))

    ema12 = spx_close.ewm(span=12).mean()
    ema26 = spx_close.ewm(span=26).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9).mean()

    bb_mid = spx_close.rolling(20).mean()
    bb_std = spx_close.rolling(20).std()
    bb_upper = float((bb_mid + 2*bb_std).iloc[-1])
    bb_lower = float((bb_mid - 2*bb_std).iloc[-1])
    bb_pct = (close - bb_lower) / (bb_upper - bb_lower) * 100 if (bb_upper - bb_lower) > 0 else 50

    low14 = spx_low.rolling(14).min()
    high14 = spx_high.rolling(14).max()
    rsv = (spx_close - low14) / (high14 - low14) * 100
    k = rsv.ewm(com=2).mean()
    d = k.ewm(com=2).mean()

    recent = []
    n = min(5, len(spx_close))
    for i in range(n):
        idx = -(n - i)
        recent.append({
            "date": str(raw_spx.index[idx].date()),
            "open": round(float(spx_open.iloc[idx]), 2),
            "high": round(float(spx_high.iloc[idx]), 2),
            "low": round(float(spx_low.iloc[idx]), 2),
            "close": round(float(spx_close.iloc[idx]), 2),
            "volume": int(spx_vol.iloc[idx])
        })

    vix_close = raw_vix["Close"].squeeze()
    vix_val = float(vix_close.iloc[-1]) if not vix_close.empty else 0

    result = {
        "trade_date": str(raw_spx.index[-1].date()),
        "close": round(close, 2),
        "open": round(float(spx_open.iloc[-1]), 2),
        "high": round(float(spx_high.iloc[-1]), 2),
        "low": round(float(spx_low.iloc[-1]), 2),
        "volume": int(spx_vol.iloc[-1]),
        "prev_close": round(prev_close, 2),
        "change_pct": round(change_pct, 2),
        "vix": round(vix_val, 2),
        "ma5": round(sma(5), 2),
        "ma20": round(sma(20), 2),
        "ma50": round(sma(50), 2),
        "ma200": round(sma(200), 2),
        "rsi": round(rsi, 2),
        "macd_hist": round(float((macd_line - signal_line).iloc[-1]), 2),
        "macd_line": round(float(macd_line.iloc[-1]), 2),
        "signal": round(float(signal_line.iloc[-1]), 2),
        "bb_upper": round(bb_upper, 2),
        "bb_lower": round(bb_lower, 2),
        "bb_pct": round(bb_pct, 1),
        "kd_k": round(float(k.iloc[-1]), 2),
        "kd_d": round(float(d.iloc[-1]), 2),
        "recent_5": recent
    }

with open(os.path.join(OUT_DIR, "today_data.txt"), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
