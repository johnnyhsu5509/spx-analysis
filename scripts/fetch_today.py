import yfinance as yf
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import yf_compat
import json
import os
import sys
from datetime import datetime, timedelta

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(OUT_DIR)

def _use_snapshot():
    """Fetch failed: fall back to the Actions-committed snapshot in data/."""
    snap = os.path.join(REPO, "data", "today_data.txt")
    try:
        with open(snap, encoding="utf-8") as f:
            d = json.load(f)
        if not d.get("trade_date"):
            return False
        import shutil
        shutil.copy(snap, os.path.join(OUT_DIR, "today_data.txt"))
        fa = os.path.join(REPO, "data", "fetched_at.txt")
        ts = open(fa).read().strip() if os.path.exists(fa) else "unknown"
        print("OK trade_date=%s close=%s (SNAPSHOT from data/, fetched_at=%s)"
              % (d["trade_date"], d.get("close"), ts))
        print("NOTE: live fetch failed; using GitHub Actions snapshot. Verify trade_date is the expected close.")
        return True
    except Exception:
        return False


def _breadth():
    """RSP/SPY 等權 vs 市值權重比值 = 廣度代理。
    比值上升 = 中小型股同步參與(廣度好)；下降 = 少數權值撐盤(窄化)。
    抓不到不阻斷主流程,回傳 None。"""
    try:
        rsp = yf_compat.download("RSP", period="3mo", progress=False)
        spy = yf_compat.download("SPY", period="3mo", progress=False)
        for df in (rsp, spy):
            if hasattr(df.columns, "levels"):
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        r = rsp["Close"].squeeze().dropna()
        p_ = spy["Close"].squeeze().dropna()
        idx = r.index.intersection(p_.index)
        ratio = (r.loc[idx] / p_.loc[idx]).dropna()
        if len(ratio) < 25:
            return None
        cur = float(ratio.iloc[-1])
        d1 = (cur / float(ratio.iloc[-2]) - 1) * 100
        d5 = (cur / float(ratio.iloc[-6]) - 1) * 100
        ma20 = float(ratio.rolling(20).mean().iloc[-1])
        vs20 = (cur / ma20 - 1) * 100
        if d5 >= 0.5:
            read = "廣度擴張（中小型股同步參與）"
        elif d5 <= -0.5:
            read = "廣度窄化（少數權值撐盤，指數強度打折）"
        else:
            read = "廣度中性"
        return {
            "rsp_spy_ratio": round(cur, 4),
            "chg_1d_pct": round(d1, 2),
            "chg_5d_pct": round(d5, 2),
            "vs_ma20_pct": round(vs20, 2),
            "read": read,
            "note": "RSP(等權)/SPY(市值權重);升=廣度好,降=窄化。與指數方向背離時,指數漲勢品質打折"
        }
    except Exception:
        return None


end = datetime.today() + timedelta(days=1)
start = end - timedelta(days=300)

try:
    raw_spx = yf_compat.download("^GSPC", start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), progress=False)
    raw_vix = yf_compat.download("^VIX", start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), progress=False)
except Exception as exc:
    if _use_snapshot():
        sys.exit(0)
    print("FETCH FAILED (network/yfinance): %r" % (exc,))
    print("today_data.txt left UNCHANGED. Check egress allowlist:")
    print("  query1.finance.yahoo.com / query2.finance.yahoo.com / fc.yahoo.com")
    sys.exit(1)

if raw_spx is None or raw_spx.empty:
    if _use_snapshot():
        sys.exit(0)
    print("FETCH FAILED: empty dataframe for ^GSPC (blocked or no data)")
    print("today_data.txt left UNCHANGED. Check egress allowlist:")
    print("  query1.finance.yahoo.com / query2.finance.yahoo.com / fc.yahoo.com")
    sys.exit(1)

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

    # === Regime 分類 ===
    # 歷史拉回率由 backtest.py 產出並存入 docs/regime_baseline.json，此處直接讀取。
    # 每季重跑 backtest.py 即自動更新，無需手改本檔。缺檔時用內建 fallback。
    # 定義：5日內盤中低點 <= 訊號日收盤 -0.75%；超額 = 該 regime 拉回率 - 全體基準率。
    DEFAULT_C = {"BASE_5D": 61.65,
                 "vix": {"vix_lt16": 49.45, "vix_16_20": 63.08, "vix_ge20": 71.15},
                 "trend": {"above_ma200": 56.95, "below_ma200": 75.68},
                 "ext": {"ma20_over3": 60.58, "ma20_normal": 59.89, "ma20_under3": 77.48}}
    try:
        with open(os.path.join(REPO, "docs", "regime_baseline.json"), encoding="utf-8") as bf:
            C = json.load(bf).get("fetch_today_constants", DEFAULT_C)
    except Exception:
        C = DEFAULT_C

    BASE_5D = C["BASE_5D"]
    ma20_v = sma(20)
    ma200_v = sma(200)
    ma20_ext = (close - ma20_v) / ma20_v * 100

    if vix_val < 16:
        vix_reg, vix_rate = "VIX<16（低波動）", C["vix"]["vix_lt16"]
    elif vix_val < 20:
        vix_reg, vix_rate = "VIX 16-20（中波動）", C["vix"]["vix_16_20"]
    else:
        vix_reg, vix_rate = "VIX>=20（高波動）", C["vix"]["vix_ge20"]

    if close >= ma200_v:
        trend_reg, trend_rate = "SPX 在 MA200 之上（多頭結構）", C["trend"]["above_ma200"]
    else:
        trend_reg, trend_rate = "SPX 在 MA200 之下（空頭結構）", C["trend"]["below_ma200"]

    if ma20_ext >= 3:
        ext_reg, ext_rate = "距 MA20 +3% 以上（過度延伸）", C["ext"]["ma20_over3"]
    elif ma20_ext <= -3:
        ext_reg, ext_rate = "距 MA20 -3% 以下（深跌）", C["ext"]["ma20_under3"]
    else:
        ext_reg, ext_rate = "距 MA20 +/-3% 內（正常）", C["ext"]["ma20_normal"]

    regime_avg = round((vix_rate + trend_rate + ext_rate) / 3, 1)
    regime = {
        "base_5d_pullback": BASE_5D,
        "vix": {"regime": vix_reg, "pullback_5d": vix_rate, "vs_base": round(vix_rate - BASE_5D, 1)},
        "trend": {"regime": trend_reg, "pullback_5d": trend_rate, "vs_base": round(trend_rate - BASE_5D, 1)},
        "ma20_ext": {"regime": ext_reg, "pullback_5d": ext_rate, "vs_base": round(ext_rate - BASE_5D, 1), "ext_pct": round(ma20_ext, 2)},
        "regime_avg_5d": regime_avg,
        "regime_avg_vs_base": round(regime_avg - BASE_5D, 1)
    }

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
        "breadth": _breadth(),
        "regime": regime,
        "recent_5": recent
    }

if not result or not result.get("trade_date"):
    print("FETCH FAILED: no trade_date computed; today_data.txt left UNCHANGED")
    sys.exit(1)

with open(os.path.join(OUT_DIR, "today_data.txt"), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("OK trade_date=%s close=%s" % (result.get("trade_date"), result.get("close")))
