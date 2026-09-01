import yfinance as yf
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import yf_compat
import guard
import gap_fix
import json
import os
import sys
from datetime import datetime, timedelta

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(OUT_DIR)

# ---------------------------------------------------------------------------
# 標的設定。SPX 為預設，行為與參數化前完全相同（回歸測試比對過）。
# NDX 為 2026-08-18 新增，與 SPX 兩套並列不分主從。
# 門檻由 calibrate_ndx*.py 校準，不是沿用 VIX 的 16/20 —— 詳見 backtest_ndx.py。
# ---------------------------------------------------------------------------
SYMBOLS = {
    "spx": {
        "index": "^GSPC", "vol": "^VIX", "vol_key": "vix", "label": "SPX",
        "cuts": (16, 20),
        "cut_labels": ("VIX<16（低波動）", "VIX 16-20（中波動）", "VIX>=20（高波動）"),
        "bucket_keys": ("vix_lt16", "vix_16_20", "vix_ge20"),
        "baseline": "regime_baseline.json",
        "outfile": "today_data.txt",
        "breadth": ("RSP", "SPY"),
        "breadth_note": "RSP(等權)/SPY(市值權重);升=廣度好,降=窄化。與指數方向背離時,指數漲勢品質打折",
        "pullback_txt": "-0.75%",
        "default_c": {"BASE_5D": 61.65,
                      "vix": {"vix_lt16": 49.45, "vix_16_20": 63.08, "vix_ge20": 71.15},
                      "trend": {"above_ma200": 56.95, "below_ma200": 75.68},
                      "ext": {"ma20_over3": 60.58, "ma20_normal": 59.89, "ma20_under3": 77.48}},
    },
    "ndx": {
        "index": "^NDX", "vol": "^VXN", "vol_key": "vxn", "label": "NDX",
        "cuts": (18, 28),
        "cut_labels": ("VXN<18（低波動）", "VXN 18-28（中波動）", "VXN>=28（高波動）"),
        "bucket_keys": ("vxn_lt18", "vxn_18_28", "vxn_ge28"),
        "baseline": "ndx_regime_baseline.json",
        "outfile": "ndx_today_data.txt",
        "breadth": ("QQQE", "QQQ"),
        "breadth_note": "QQQE(等權NDX)/QQQ(市值權重);升=廣度好,降=窄化。科技股權重極集中,窄化時指數強度打折更明顯",
        "pullback_txt": "-1.00%",
        "default_c": {"BASE_5D": 57.14,
                      "vxn": {"vxn_lt18": 40.36, "vxn_18_28": 61.47, "vxn_ge28": 72.35},
                      "trend": {"above_ma200": 53.46, "below_ma200": 73.68},
                      "ext": {"ma20_over3": 60.74, "ma20_normal": 53.51, "ma20_under3": 73.31}},
    },
}

_argv = [a for a in sys.argv[1:]]
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
VOL_KEY = CFG["vol_key"]
LO_CUT, HI_CUT = CFG["cuts"]
B_LO, B_MID, B_HI = CFG["bucket_keys"]
OUTFILE = CFG["outfile"]
guard.check_ticker(CFG["label"], CFG["index"])   # 設定被改錯時不准抓


def _use_snapshot():
    """Fetch failed: fall back to the Actions-committed snapshot in data/."""
    snap = os.path.join(REPO, "data", OUTFILE)
    try:
        with open(snap, encoding="utf-8") as f:
            d = json.load(f)
        if not d.get("trade_date"):
            return False
        import shutil
        shutil.copy(snap, os.path.join(OUT_DIR, OUTFILE))
        fa = os.path.join(REPO, "data", "fetched_at.txt")
        ts = open(fa).read().strip() if os.path.exists(fa) else "unknown"
        print("OK trade_date=%s close=%s (SNAPSHOT from data/, fetched_at=%s)"
              % (d["trade_date"], d.get("close"), ts))
        print("NOTE: live fetch failed; using GitHub Actions snapshot. Verify trade_date is the expected close.")
        return True
    except Exception:
        return False


# gap_fix 回補紀錄。非空 = 本次輸出含人工回補的日子，下游必須知道（寫進 data_integrity）。
GAP_NOTES = []


def _breadth():
    """等權 vs 市值權重比值 = 廣度代理。
    比值上升 = 中小型股同步參與(廣度好)；下降 = 少數權值撐盤(窄化)。
    抓不到不阻斷主流程,回傳 None。"""
    eq_sym, cap_sym = CFG["breadth"]
    try:
        rsp = yf_compat.download(eq_sym, period="3mo", progress=False)
        spy = yf_compat.download(cap_sym, period="3mo", progress=False)
        for df in (rsp, spy):
            if hasattr(df.columns, "levels"):
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        rsp, _n1 = gap_fix.patch_missing_days(rsp, eq_sym, log=print)
        spy, _n2 = gap_fix.patch_missing_days(spy, cap_sym, log=print)
        GAP_NOTES.extend(_n1 + _n2)
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
            "%s_%s_ratio" % (eq_sym.lower(), cap_sym.lower()): round(cur, 4),
            "chg_1d_pct": round(d1, 2),
            "chg_5d_pct": round(d5, 2),
            "vs_ma20_pct": round(vs20, 2),
            "read": read,
            "note": CFG["breadth_note"]
        }
    except Exception:
        return None


end = datetime.today() + timedelta(days=1)
start = end - timedelta(days=300)

try:
    raw_spx = yf_compat.download(CFG["index"], start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), progress=False)
    raw_vix = yf_compat.download(CFG["vol"], start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), progress=False)
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
    print("FETCH FAILED: empty dataframe for %s (blocked or no data)" % CFG["index"])
    print("today_data.txt left UNCHANGED. Check egress allowlist:")
    print("  query1.finance.yahoo.com / query2.finance.yahoo.com / fc.yahoo.com")
    sys.exit(1)

if hasattr(raw_spx.columns, 'levels'):
    raw_spx.columns = [c[0] if isinstance(c, tuple) else c for c in raw_spx.columns]
if hasattr(raw_vix.columns, 'levels'):
    raw_vix.columns = [c[0] if isinstance(c, tuple) else c for c in raw_vix.columns]

# 缺日回補（2026-09-01 新增）。Yahoo 日線曾整天遺失 2026-08-28，而 30m 完整存在；
# 舊版不會報錯，但 MA/RSI/MACD/BB/KD/ATR 與 prev_close 全部靜默錯位一天。
raw_spx, _gs = gap_fix.patch_missing_days(raw_spx, CFG["index"], log=print)
raw_vix, _gv = gap_fix.patch_missing_days(raw_vix, CFG["vol"], log=print)
GAP_NOTES.extend(_gs + _gv)

# Yahoo 常在最新一列給「未結算」資料：只有 Volume、OHLC 全 NaN。
# 不濾掉的話 close 會是 nan，而舊版完整性檢查只看 trade_date 是否存在，
# 會回報 OK 並把 nan 寫進資料檔，下游全部污染且不報錯。
_before = len(raw_spx)
raw_spx = raw_spx.dropna(subset=["Close"])
_dropped = _before - len(raw_spx)
if _dropped:
    print("[fetch] dropped %d unsettled row(s) with NaN Close (Yahoo partial data)" % _dropped)
if raw_spx.empty:
    if _use_snapshot():
        sys.exit(0)
    print("FETCH FAILED: every row has NaN Close for %s; %s left UNCHANGED"
          % (CFG["index"], OUTFILE))
    sys.exit(1)
raw_vix = raw_vix.dropna(subset=["Close"])

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
    # 歷史拉回率由 backtest.py / backtest_ndx.py 產出並存入 docs/*regime_baseline.json，
    # 此處直接讀取。每季重跑即自動更新，無需手改本檔。缺檔時用內建 fallback。
    # 定義：5日內盤中低點 <= 訊號日收盤 -0.75%(SPX) / -1.00%(NDX)；
    #       超額 = 該 regime 拉回率 - 全體基準率。
    #       NDX 用較寬的門檻是因為其日波動為 SPX 的 1.25-1.37 倍，
    #       沿用 -0.75% 會讓兩套系統的機率不可比。
    DEFAULT_C = CFG["default_c"]
    try:
        with open(os.path.join(REPO, "docs", CFG["baseline"]), encoding="utf-8") as bf:
            C = json.load(bf).get("fetch_today_constants", DEFAULT_C)
    except Exception:
        C = DEFAULT_C

    BASE_5D = C["BASE_5D"]
    ma20_v = sma(20)
    ma200_v = sma(200)
    ma20_ext = (close - ma20_v) / ma20_v * 100

    lab_lo, lab_mid, lab_hi = CFG["cut_labels"]
    if vix_val < LO_CUT:
        vix_reg, vix_rate = lab_lo, C[VOL_KEY][B_LO]
    elif vix_val < HI_CUT:
        vix_reg, vix_rate = lab_mid, C[VOL_KEY][B_MID]
    else:
        vix_reg, vix_rate = lab_hi, C[VOL_KEY][B_HI]

    if close >= ma200_v:
        trend_reg, trend_rate = "%s 在 MA200 之上（多頭結構）" % CFG["label"], C["trend"]["above_ma200"]
    else:
        trend_reg, trend_rate = "%s 在 MA200 之下（空頭結構）" % CFG["label"], C["trend"]["below_ma200"]

    if ma20_ext >= 3:
        ext_reg, ext_rate = "距 MA20 +3% 以上（過度延伸）", C["ext"]["ma20_over3"]
    elif ma20_ext <= -3:
        ext_reg, ext_rate = "距 MA20 -3% 以下（深跌）", C["ext"]["ma20_under3"]
    else:
        ext_reg, ext_rate = "距 MA20 +/-3% 內（正常）", C["ext"]["ma20_normal"]

    regime_avg = round((vix_rate + trend_rate + ext_rate) / 3, 1)
    regime = {
        "base_5d_pullback": BASE_5D,
        VOL_KEY: {"regime": vix_reg, "pullback_5d": vix_rate, "vs_base": round(vix_rate - BASE_5D, 1)},
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
        VOL_KEY: round(vix_val, 2),
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
    # 缺日回補紀錄。有值 = 本份資料含人工回補的交易日，分析時必須在報告標明。
    if GAP_NOTES:
        result["data_integrity"] = {
            "status": "PATCHED",
            "patched_days": GAP_NOTES,
            "note": "Yahoo 日線缺日已由 gap_fix.py 回補（依據：該日 30m 有資料 = 確實有交易）。"
                    "分析報告必須標明本次使用了回補資料。"
        }
    # 每份輸出都蓋上 symbol，供下游 guard.require_symbol 驗證來源（兩套皆蓋）
    guard.stamp(result, CFG["label"])

if not result or not result.get("trade_date"):
    print("FETCH FAILED: no trade_date computed; %s left UNCHANGED" % OUTFILE)
    sys.exit(1)

# 完整性把關：close 為 NaN 代表抓到未結算/殘缺資料，寫出去會靜默污染下游。
# 舊版只檢查 trade_date，NaN 會一路寫進檔案並回報 OK（2026-08-18 實際發生）。
_bad = [k for k in ("close", "open", "high", "low", "prev_close", "ma5", "ma20")
        if result.get(k) is None or result.get(k) != result.get(k)]
if _bad:
    print("FETCH FAILED: NaN/missing in %s for %s; %s left UNCHANGED"
          % (",".join(_bad), CFG["label"], OUTFILE))
    print("CAUSE: Yahoo returned unsettled rows. Retry later, or use the data/ snapshot.")
    sys.exit(1)

with open(os.path.join(OUT_DIR, OUTFILE), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

# 寫完立刻交叉檢查：兩套的資料檔不可有相同收盤（相同＝互相覆寫）
guard.cross_check(OUT_DIR)

print("OK symbol=%s trade_date=%s close=%s"
      % (CFG["label"], result.get("trade_date"), result.get("close")))
