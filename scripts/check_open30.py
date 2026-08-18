import yfinance as yf
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import yf_compat
import json
import os
import sys
from datetime import datetime

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# 標的設定。SPX 為預設（行為與參數化前相同）；NDX 為 2026-08-18 新增。
# 類股同步檢查（rule15）在兩套用不同對照組：
#   SPX -> ^IXIC(那斯達克) + SOXX(半導體)：檢查大盤綠燈是否被科技拖累
#   NDX -> SOXX(半導體) + QQQE(等權NDX)：^IXIC 對 NDX 幾乎同義無資訊，
#          改用等權看是否只有少數權值撐盤
# 已知限制：量能取指數成交量，yfinance 偶爾不準或為 0 -> 量能僅供參考。
# ---------------------------------------------------------------------------
SYMBOLS = {
    "spx": {"index": "^GSPC", "label": "SPX",
            "sync": [("^IXIC", "nasdaq"), ("SOXX", "soxx_semis")],
            "vol": ("^VIX", "vix"), "outfile": "open30_check.txt"},
    "ndx": {"index": "^NDX", "label": "NDX",
            "sync": [("SOXX", "soxx_semis"), ("QQQE", "qqq_equalweight")],
            "vol": ("^VXN", "vxn"), "outfile": "ndx_open30_check.txt"},
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
INDEX, LABEL = CFG["index"], CFG["label"]
VOL_TICK, VOL_KEY = CFG["vol"]
OUTFILE = CFG["outfile"]

result = {"checked_at": datetime.now().strftime("%Y-%m-%d %H:%M")}


def bars_30m(ticker, period="10d"):
    raw = yf_compat.download(ticker, period=period, interval="30m", progress=False)
    if hasattr(raw.columns, 'levels'):
        raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]
    return raw


spx_first_dir = None
today = None

try:
    raw = bars_30m(INDEX)
    dates = sorted({i.date() for i in raw.index})
    today = dates[-1]
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
        spx_first_dir = "UP" if first["close"] > first["open"] else "DOWN" if first["close"] < first["open"] else "FLAT"
        result["first_30m_direction"] = spx_first_dir
        result["first_30m_range"] = {"high": first["high"], "low": first["low"]}
        result["first_30m_volume"] = first["volume"]

        # 首30分量能 vs 近5日同時段基準（不再憑感覺比）
        prev_days = dates[:-1][-5:]
        vols = []
        for d in prev_days:
            db = raw[[i.date() == d for i in raw.index]]
            if len(db):
                vols.append(int(db.iloc[0]["Volume"]))
        if vols:
            avg5 = sum(vols) / len(vols)
            ratio = first["volume"] / avg5 if avg5 else None
            result["first_30m_vol_avg5d"] = int(avg5)
            result["first_30m_vol_ratio"] = round(ratio, 2) if ratio else None
            result["first_30m_vol_read"] = ("放量" if ratio >= 1.2 else
                                            "量不足(假動作風險)" if ratio < 0.75 else "正常")
except Exception as e:
    result["error"] = str(e)

# 科技/半導體同步檢查（rule15：指數綠燈但類股跳水=對重倉者無效綠燈）
sync = {}
for ticker, key in CFG["sync"]:
    try:
        raw2 = bars_30m(ticker, "5d")
        tb = raw2[[i.date() == today for i in raw2.index]]
        if len(tb):
            fb = tb.iloc[0]
            chg = round(float((fb["Close"] - fb["Open"]) / fb["Open"] * 100), 2)
            sync[key] = {"first_30m_pct": chg,
                         "direction": "UP" if chg > 0.05 else "DOWN" if chg < -0.05 else "FLAT"}
    except Exception:
        pass
if sync:
    result["sector_sync"] = sync
    dirs = {v["direction"] for v in sync.values() if v["direction"] != "FLAT"}
    if spx_first_dir and spx_first_dir != "FLAT" and dirs and (spx_first_dir not in dirs or len(dirs) > 1):
        result["sync_read"] = "DIVERGENT：%s與科技/半導體方向背離，開盤確認降級為觀望（rule15）" % LABEL
    elif spx_first_dir:
        result["sync_read"] = "SYNC：指數與科技/半導體同向，訊號有效"

try:
    vx = yf_compat.ticker(VOL_TICK)
    result[VOL_KEY] = round(float(vx.fast_info["last_price"]), 2)
except Exception:
    pass

with open(os.path.join(OUT_DIR, OUTFILE), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

# 原版寫完就靜默結束，抓取失敗時無從察覺；補上狀態行（不改動 JSON 內容）
if result.get("error") or not result.get("bars_30m"):
    print("CHECK_OPEN30 FAILED (%s): %s" % (LABEL, result.get("error", "no bars returned")))
    sys.exit(1)
print("OK %s session_date=%s first_30m=%s" % (LABEL, result.get("session_date"), result.get("first_30m_direction")))
