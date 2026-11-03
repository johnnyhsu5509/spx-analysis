"""排程瘦身腳本共用：帳本讀寫、交易日、判定 session、影子單成交、深度合併、數值比對。"""
import datetime
import json
import math
from decimal import ROUND_HALF_UP, Decimal


def ld(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def sv(p, o):
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(o, ensure_ascii=False, indent=1))


def next_bday(d):
    t = datetime.date.fromisoformat(d) + datetime.timedelta(days=1)
    while t.weekday() >= 5:
        t += datetime.timedelta(days=1)
    return t.isoformat()


def md(d):
    t = datetime.date.fromisoformat(d[:10])
    return f'{t.month}/{t.day}'


def eval_session(td, target):
    """待判定預測的目標 session：通常就是 today_data 當天；中間漏跑（gap day）時從 recent_5 取，並回傳 gap day 清單。"""
    day = td['trade_date']
    if target == day:
        return {'o': td['open'], 'h': td['high'], 'l': td['low'], 'c': td['close'], 'pc': td['prev_close'], 'chg': td.get('change_pct')}, []
    rows = td.get('recent_5') or []
    idx = [i for i, r in enumerate(rows) if r['date'] == target]
    if target > day or not idx or idx[0] == 0 or rows[-1]['date'] != day:
        raise SystemExit(f'待判定預測的目標日 {target} 不在 today_data（{day}）的 recent_5 裡，請人工記帳')
    i = idx[0]
    r, pc = rows[i], rows[i - 1]['close']
    return {'o': r['open'], 'h': r['high'], 'l': r['low'], 'c': r['close'], 'pc': pc, 'chg': None}, [x['date'] for x in rows[i + 1:]]


def shadow_fill(side, lim, a, s, o, h, lo, c):
    """影子單：成交價＝min／max(掛單價, 開盤價)，停損優先，否則收盤平倉。未成交回傳 None。"""
    if side == 'long':
        if lo > lim:
            return None
        fill = min(lim, o)
        stop = round(fill - s * a, 2)
        hit = lo <= stop
        ex = stop if hit else c
        pts = round(ex - fill, 2)
    else:
        if h < lim:
            return None
        fill = max(lim, o)
        stop = round(fill + s * a, 2)
        hit = h >= stop
        ex = stop if hit else c
        pts = round(fill - ex, 2)
    return {'fill': fill, 'gap': fill != lim, 'stop': stop, 'stop_hit': hit, 'exit': ex, 'pnl_pts': pts, 'pnl_A': round(pts / a, 3)}


def hu(x, nd=1):
    """一般四捨五入（浮點格式遇 .5 不一定進位）。"""
    return float(Decimal(str(x)).quantize(Decimal(1).scaleb(-nd), ROUND_HALF_UP))


def log_err(actual, ref):
    return round(abs(math.log(actual / ref)), 4)


def merge(dst, src, shallow, deep=()):
    """src 的頂層鍵整段取代；shallow 列出的鍵只覆蓋給到的子鍵，deep 列出的鍵再往下一層。"""
    for k, v in src.items():
        if k in shallow and isinstance(v, dict) and isinstance(dst.get(k), dict):
            for kk, vv in v.items():
                if k in deep and isinstance(vv, dict) and isinstance(dst[k].get(kk), dict):
                    dst[k][kk].update(vv)
                else:
                    dst[k][kk] = vv
        else:
            dst[k] = v
    return dst


def is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def walk_diffs(a, b, path=''):
    """逐欄比對 a（腳本）與 b（實跑）。回傳 (kind, path, a, b)：kind ∈ value／only_mech／only_actual／length。"""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in list(b) + [k for k in a if k not in b]:
            p = f'{path}.{k}' if path else k
            if k not in a:
                out.append(('only_actual', p, None, b[k]))
            elif k not in b:
                out.append(('only_mech', p, a[k], None))
            else:
                out += walk_diffs(a[k], b[k], p)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(('length', path, len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            out += walk_diffs(x, y, f'{path}[{i}]')
    elif a != b or isinstance(a, bool) != isinstance(b, bool):
        out.append(('value', path, a, b))
    return out


def numeric(d, tol=0.0):
    """只留數值差異：任一邊是數字／布林／null 對數字，或筆數不同；|差| ≤ tol 視為相同。"""
    kind, _, a, b = d
    if kind == 'length':
        return True
    if kind in ('only_mech', 'only_actual'):
        v = a if kind == 'only_mech' else b
        return is_num(v) or isinstance(v, bool)
    if isinstance(a, str) or isinstance(b, str) or isinstance(a, (dict, list)) or isinstance(b, (dict, list)):
        return False
    if is_num(a) and is_num(b):
        return abs(a - b) > tol
    return True
