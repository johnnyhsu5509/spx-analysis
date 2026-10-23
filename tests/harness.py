"""測試共用：合成行情、假 yfinance fixture、在暫存目錄執行新版或原版（git ref）腳本。全程不連網。"""
import collections
import copy
import json
import math
import os
import pickle
import random
import subprocess
import sys
import tempfile

import pandas as pd

TESTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TESTS)
SCRIPTS = os.path.join(REPO, "scripts")
RUNNER = os.path.join(TESTS, "stubs", "run.py")
BASELINE_REF = os.environ.get("BASELINE_REF", "origin/main")
MODULES = ("fetch_today.py", "check_es.py", "guard.py", "gap_fix.py", "yf_compat.py", "wilder.py", "cme_session.py")
OUTPUTS = ("today_data.txt", "ndx_today_data.txt", "es_check.txt", "ndx_es_check.txt")
sys.path.insert(0, SCRIPTS)

Result = collections.namedtuple("Result", "code out err files")

DAYS = pd.bdate_range("2025-06-02", periods=330, name="Date")
SYMBOLS = {
    "spx": {"index": ("^GSPC", 6000.0), "vol": ("^VIX", 17.0), "breadth": (("RSP", 180.0), ("SPY", 600.0)),
            "baseline": "regime_baseline.json", "vol_key": "vix", "buckets": ("vix_lt16", "vix_16_20", "vix_ge20")},
    "ndx": {"index": ("^NDX", 21000.0), "vol": ("^VXN", 22.0), "breadth": (("QQQE", 95.0), ("QQQ", 520.0)),
            "baseline": "ndx_regime_baseline.json", "vol_key": "vxn", "buckets": ("vxn_lt18", "vxn_18_28", "vxn_ge28")},
}
# 覆寫指數末段報酬：index -15 的漲跌今天滑出 Cutler 的 14 日窗口，index -1 為當日
TAILS = {
    "diverge": {-15: -0.045, -1: -0.006},  # 大黑 K 滑出、當日小跌 → Cutler 升、Wilder 降（2026-08-18 型）
    "agree": {-15: 0.001, -1: 0.012},      # 小漲滑出、當日大漲 → 兩者同升
}


def walk(seed, sd=0.008):
    rnd = random.Random(seed)
    return [rnd.gauss(0.0004, sd) for _ in DAYS]


def bars(returns, start, seed):
    rnd = random.Random(seed)
    rows, c = [], start
    for r in returns:
        o = c * (1 + rnd.uniform(-0.002, 0.002))
        c *= 1 + r
        rows.append((o, max(o, c) * (1 + rnd.uniform(0, 0.004)), min(o, c) * (1 - rnd.uniform(0, 0.004)), c,
                     rnd.randint(2 * 10 ** 9, 5 * 10 ** 9)))
    return pd.DataFrame(rows, index=DAYS[:len(returns)], columns=["Open", "High", "Low", "Close", "Volume"])


def vol_bars(base):
    lvl = [base + 3 * math.sin(i / 17) + 0.5 * math.sin(i / 3.1) for i in range(len(DAYS))]
    return pd.DataFrame({"Open": lvl, "High": lvl, "Low": lvl, "Close": lvl, "Volume": 0}, index=DAYS)


def intraday(df, days=40):
    t = df.iloc[-days:].copy()
    t.index = t.index + pd.Timedelta(hours=15, minutes=30)
    return t


def fetch_fixture(sym="spx", tail=None, gap=False):
    """fetch_today.py 用。gap=True：指數與波動指數中間缺一天（30m 有）、等權 ETF 末日缺（測 gap_fix 與 rule51 補值路徑）。"""
    s = SYMBOLS[sym]
    ret = walk(1 if sym == "spx" else 2)
    for i, r in TAILS.get(tail, {}).items():
        ret[i] = r
    idx, vol, eq = s["index"][0], s["vol"][0], s["breadth"][0][0]
    full = {idx: bars(ret, s["index"][1], 11), vol: vol_bars(s["vol"][1])}
    for j, (t, p) in enumerate(s["breadth"]):
        full[t] = bars(walk(20 + j, 0.006), p, 30 + j)
    daily = dict(full)
    if gap:
        daily[idx], daily[vol] = full[idx].drop(DAYS[-10]), full[vol].drop(DAYS[-10])
        daily[eq] = full[eq].iloc[:-1]
    return {"daily": daily, "intraday": {t: intraday(df) for t, df in full.items()}, "quote": {}}


def with_nan(fx, col, rows, ticker="^GSPC"):
    fx = copy.deepcopy(fx)
    df = fx["daily"][ticker]
    df.iloc[rows, df.columns.get_loc(col)] = float("nan")
    return fx


def es_fixture():
    """check_es.py 用：即時報價與 15m 期貨（含前一交易日 16:00 ET 錨點）。"""
    t = pd.date_range("2026-10-22 12:00", periods=97, freq="15min", tz="America/New_York")

    def line(a, b):
        c = [a + (b - a) * i / (len(t) - 1) for i in range(len(t))]
        return pd.DataFrame({"Open": c, "High": c, "Low": c, "Close": c, "Volume": 0}, index=t)

    return {"daily": {}, "intraday": {"ES=F": line(7706.0, 7701.75), "NQ=F": line(26480.0, 26000.0)},
            "quote": {"ES=F": (7701.75, 7750.75), "NQ=F": (26000.0, 26500.0), "SOXX": (475.69, 502.36),
                      "^VIX": (19.03, 18.2), "^VXN": (25.1, 24.0), "^TNX": (4.953, 5.146), "DX-Y.NYB": (101.58, 101.6)}}


ES_FILES = {"scripts/today_data.txt": {"trade_date": "2026-10-22", "close": 7663.43, "symbol": "SPX"},
            "scripts/ndx_today_data.txt": {"trade_date": "2026-10-22", "close": 29400.12, "symbol": "NDX"}}


def ref_wilder(closes, n=14):
    """Wilder 原始定義的逐筆實作（獨立於 scripts/wilder.py），回傳對齊 closes[n:] 的 list。"""
    ch = [b - a for a, b in zip(closes, closes[1:])]
    ag = sum(max(x, 0.0) for x in ch[:n]) / n
    al = sum(max(-x, 0.0) for x in ch[:n]) / n
    out = [100.0 if al == 0 else 100 - 100 / (1 + ag / al)]
    for x in ch[n:]:
        ag = (ag * (n - 1) + max(x, 0.0)) / n
        al = (al * (n - 1) + max(-x, 0.0)) / n
        out.append(100.0 if al == 0 else 100 - 100 / (1 + ag / al))
    return out


def cutler(close):
    """與 fetch_today.py 的 rsi 欄位同一公式（簡單 14 日均）。"""
    d = close.diff()
    return 100 - 100 / (1 + d.clip(lower=0).rolling(14).mean() / (-d.clip(upper=0)).rolling(14).mean())


def has_baseline():
    try:
        p = subprocess.run(["git", "cat-file", "-e", "%s:scripts/fetch_today.py" % BASELINE_REF],
                           cwd=REPO, capture_output=True, encoding="utf-8")
    except OSError:
        return False
    return p.returncode == 0


def _source(module, ref):
    if ref is None:
        with open(os.path.join(SCRIPTS, module), encoding="utf-8") as f:
            return f.read()
    p = subprocess.run(["git", "show", "%s:scripts/%s" % (ref, module)], cwd=REPO, capture_output=True, encoding="utf-8")
    return p.stdout if p.returncode == 0 else None


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, indent=2))


def _baseline(vol_key, buckets):
    return {
        "fetch_today_constants": {"BASE_5D": 60.0, vol_key: dict(zip(buckets, (50.0, 63.0, 71.0))),
                                  "trend": {"above_ma200": 57.0, "below_ma200": 75.0},
                                  "ext": {"ma20_over3": 60.0, "ma20_normal": 59.0, "ma20_under3": 77.0}},
        "fetch_today_constants_1d": {"BASE_1D": 32.0, vol_key: dict(zip(buckets, (20.0, 30.0, 48.0))),
                                     "trend": {"above_ma200": 26.0, "below_ma200": 54.0},
                                     "ext": {"ma20_over3": 33.0, "ma20_normal": 30.0, "ma20_under3": 58.0}},
    }


def run(script, fx, args=(), ref=None, now_utc=None, files=None):
    """在全新暫存樹執行一次。ref=None 用工作目錄版本，否則用該 git ref 的版本。
    files：執行前寫入的 {相對路徑: 內容}。回傳 Result(code, out, err, files={輸出檔名: 文字})。"""
    with tempfile.TemporaryDirectory() as root:
        for m in MODULES:
            src = _source(m, ref)
            if src is not None:
                _write(os.path.join(root, "scripts", m), src)
        for s in SYMBOLS.values():
            _write(os.path.join(root, "docs", s["baseline"]), _baseline(s["vol_key"], s["buckets"]))
        os.makedirs(os.path.join(root, "data"))
        for rel, content in (files or {}).items():
            _write(os.path.join(root, rel), content)
        fxp = os.path.join(root, "fixture.pkl")
        with open(fxp, "wb") as f:
            pickle.dump(fx, f)
        env = dict(os.environ, YF_FIXTURE=fxp, PYTHONIOENCODING="utf-8")
        env.pop("FAKE_NOW_UTC", None)
        if now_utc:
            env["FAKE_NOW_UTC"] = now_utc
        p = subprocess.run([sys.executable, RUNNER, os.path.join(root, "scripts", script)] + list(args),
                           cwd=root, env=env, capture_output=True, encoding="utf-8", timeout=180)
        outs = {}
        for name in OUTPUTS:
            path = os.path.join(root, "scripts", name)
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    outs[name] = f.read()
        return Result(p.returncode, p.stdout, p.stderr, outs)
