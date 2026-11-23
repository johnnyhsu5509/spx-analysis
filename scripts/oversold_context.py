# -*- coding: utf-8 -*-
"""超跌情境條件統計（描述性，不改方向 50、不改部位水位、不產生交易指令）。

回答「現在這種超跌狀態，歷史上之後通常怎麼走」。這是描述統計，不是已核准的方向規則：
prc-010 的方向規則核准門檻（walk-forward、BH、扣成本後 95% 區間不含 0）本腳本沒有做，
輸出不得用來讓 direction 偏離 50。

條件（2026-11-23 寫死，跑結果之前定義，不得看結果後調整）：
  dist   = close / MA200 - 1
  volpct = 波動指數（NDX 用 ^VXN、SPX 用 ^VIX）在近 252 個交易日中的百分位
  訊號日 = dist <= DIST_TH 且 volpct >= 95
  DIST_TH：NDX -10%、SPX -5%（兩者約為各自歷史 dist 分布的同一尾端；見 dist_pctile 輸出）
事件（episode）：訊號日之間相隔 >= 20 個交易日才算新事件；以每個事件的第一個訊號日計，
  避免同一段崩跌的連續訊號日重複計數。另附「所有訊號日」版本供對照（樣本高度相關）。
結果：之後 5／20／60 個交易日的收盤報酬；之後 20／60 日內相對訊號日收盤的最大跌幅；
  之後 20 日內是否再創收盤新低（低於訊號日收盤）。基準＝全樣本所有交易日的同一統計。

用法：python3 scripts/oversold_context.py --symbol ndx|spx [--asof YYYY-MM-DD]
輸出：docs/ndx_oversold_context.json 或 docs/oversold_context.json（UTF-8），stdout 只印 ASCII。
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yf_compat  # noqa: E402

CFG = {
    'ndx': {'index': '^NDX', 'vol': '^VXN', 'dist_th': -0.10, 'out': 'ndx_oversold_context.json'},
    'spx': {'index': '^GSPC', 'vol': '^VIX', 'dist_th': -0.05, 'out': 'oversold_context.json'},
}
VOL_PCT_TH = 95.0
EPISODE_GAP = 20
HORIZONS = (5, 20, 60)
DD_WINDOWS = (20, 60)


def _close(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df['Close'].astype(float).dropna()


def load(sym, start='1985-01-01', cache_dir=None):
    path = os.path.join(cache_dir, sym.replace('^', '') + '.csv') if cache_dir else None
    if path and os.path.exists(path):
        return pd.read_csv(path, index_col=0, parse_dates=True)['close']
    df = yf_compat.download(sym, start=start, progress=False, auto_adjust=False)
    if df is None or df.empty:
        raise SystemExit('fetch failed: ' + sym)
    s = _close(df)
    if path:
        os.makedirs(cache_dir, exist_ok=True)
        s.rename('close').to_csv(path)
    return s


def build(px, vol):
    df = pd.DataFrame({'close': px}).join(pd.DataFrame({'vol': vol}), how='left')
    df['ma200'] = df['close'].rolling(200).mean()
    df['dist'] = df['close'] / df['ma200'] - 1
    # 近 252 日百分位（含當日）：當日值 >= 窗口內多少比例
    df['volpct'] = df['vol'].rolling(252).apply(lambda w: (w <= w[-1]).mean() * 100, raw=True)
    c = df['close'].values
    n = len(c)
    for h in HORIZONS:
        fwd = np.full(n, np.nan)
        fwd[:n - h] = c[h:] / c[:n - h] - 1
        df['fwd%d' % h] = fwd
    for w in DD_WINDOWS:
        dd = np.full(n, np.nan)
        for i in range(n - w):
            dd[i] = c[i + 1:i + 1 + w].min() / c[i] - 1
        df['mdd%d' % w] = dd
    df['newlow20'] = (df['mdd20'] < 0).where(df['mdd20'].notna())
    return df


def stats(sub):
    out = {'n': int(len(sub))}
    for h in HORIZONS:
        s = sub['fwd%d' % h].dropna()
        out['fwd%d' % h] = None if s.empty else {
            'n': int(len(s)), 'median_pct': round(s.median() * 100, 2), 'mean_pct': round(s.mean() * 100, 2),
            'win_rate_pct': round((s > 0).mean() * 100, 1),
            'p10_pct': round(s.quantile(0.10) * 100, 2), 'p90_pct': round(s.quantile(0.90) * 100, 2),
        }
    for w in DD_WINDOWS:
        s = sub['mdd%d' % w].dropna()
        out['mdd%d' % w] = None if s.empty else {
            'n': int(len(s)), 'median_pct': round(s.median() * 100, 2),
            'p10_pct': round(s.quantile(0.10) * 100, 2), 'worst_pct': round(s.min() * 100, 2),
        }
    s = sub['newlow20'].dropna()
    out['new_close_low_within_20d_pct'] = None if s.empty else round(s.astype(float).mean() * 100, 1)
    return out


def episodes(sig_idx, pos):
    firsts, last = [], None
    for d in sig_idx:
        p = pos[d]
        if last is None or p - last >= EPISODE_GAP:
            firsts.append(d)
        last = p
    return firsts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--symbol', choices=['ndx', 'spx'], required=True)
    ap.add_argument('--asof', help='last settled trade date to use (YYYY-MM-DD)')
    ap.add_argument('--docs', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs'))
    ap.add_argument('--cache-dir', help='reuse/save fetched daily closes here (avoids Yahoo rate limits on reruns)')
    a = ap.parse_args()
    cfg = CFG[a.symbol]

    px, vol = load(cfg['index'], cache_dir=a.cache_dir), load(cfg['vol'], cache_dir=a.cache_dir)
    if a.asof:
        px, vol = px[:a.asof], vol[:a.asof]
    df = build(px, vol)
    valid = df.dropna(subset=['dist', 'volpct'])
    pos = {d: i for i, d in enumerate(df.index)}

    sig = valid[(valid['dist'] <= cfg['dist_th']) & (valid['volpct'] >= VOL_PCT_TH)]
    ep_days = episodes(list(sig.index), pos)
    ep = df.loc[ep_days]

    today = valid.iloc[-1]
    today_d = valid.index[-1]
    res = {
        'symbol': a.symbol.upper(),
        'purpose': '超跌情境條件統計：描述性參考，不是已核准的方向規則；不改 direction 50、不改部位水位、不產生交易指令',
        'asof': str(today_d.date()),
        'sample': {'from': str(valid.index[0].date()), 'to': str(today_d.date()), 'days': int(len(valid))},
        'condition': {
            'dist_ma200_le_pct': cfg['dist_th'] * 100, 'vol_index': cfg['vol'],
            'vol_pct_1y_ge': VOL_PCT_TH, 'episode_gap_days': EPISODE_GAP,
            'defined_on': '2026-11-23，跑結果前定義',
        },
        'today': {
            'close': round(float(today['close']), 2), 'ma200': round(float(today['ma200']), 2),
            'dist_pct': round(float(today['dist']) * 100, 2), 'vol': round(float(today['vol']), 2),
            'vol_pct_1y': round(float(today['volpct']), 1),
            'dist_pctile_in_history': round(float((valid['dist'] <= today['dist']).mean() * 100), 2),
            'condition_met': bool(today['dist'] <= cfg['dist_th'] and today['volpct'] >= VOL_PCT_TH),
        },
        'episodes': {
            'stats': stats(ep),
            'list': [{'date': str(d.date()), 'dist_pct': round(float(df.at[d, 'dist']) * 100, 1),
                      'fwd20_pct': None if pd.isna(df.at[d, 'fwd20']) else round(float(df.at[d, 'fwd20']) * 100, 1),
                      'fwd60_pct': None if pd.isna(df.at[d, 'fwd60']) else round(float(df.at[d, 'fwd60']) * 100, 1),
                      'mdd60_pct': None if pd.isna(df.at[d, 'mdd60']) else round(float(df.at[d, 'mdd60']) * 100, 1)}
                     for d in ep_days],
        },
        'all_signal_days': {'stats': stats(sig), 'note': '連續訊號日高度相關，n 不代表獨立樣本'},
        'baseline_all_days': stats(valid),
        'caveats': [
            '事件數少（見 episodes.stats.n），中位數與勝率的不確定性很大，未做顯著性檢定',
            '描述性統計，未做 walk-forward、未做多重檢定，不符合 prc-010 方向規則核准門檻',
            '樣本含長期上漲漂移，正報酬有一部分是漂移，不是超跌本身的效果',
        ],
    }
    out = os.path.join(a.docs, cfg['out'])
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print('OK %s asof=%s episodes=%d signal_days=%d -> %s' % (
        a.symbol, res['asof'], len(ep_days), len(sig), os.path.basename(out)))


if __name__ == '__main__':
    main()
