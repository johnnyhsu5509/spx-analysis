"""從某次實跑前後的帳本反推 spx_daily_mech.py 需要的 today_data 欄位（舊日子的 today_data.txt 沒有進 git）。"""
import json, os, sys
b, a = sys.argv[1], sys.argv[2]
ld = lambda d, f: json.load(open(os.path.join(d, f), encoding='utf-8'))
la_a, la_b, pnl_a = ld(a, 'last_analysis.json'), ld(b, 'last_analysis.json'), ld(a, 'pnl_ledger.json')
o = pnl_a['entries'][-2]['ohlc']
am = la_a['amplitude']
td = {'trade_date': am['basis_date'], 'open': o['o'], 'high': o['h'], 'low': o['l'], 'close': o['c'], 'prev_close': la_b['close'],
      'change_pct': la_a['change_pct'], 'vix': la_a['vix'],
      'amplitude': {'as_of': am['basis_date'], 'amp_forecast_pct': am['A_pct'], 'band_50_pct': [am['band_lo'], am['band_hi']],
                    'r0_rule27_ref_pct': am['r0_ref_pct'], 'c': am['c'], 'vol_pct_1y': am['vol_pct_1y'],
                    'realized_vs_implied_63d': am.get('realized_vs_implied_63d')}}
json.dump(td, open(os.path.join(b, 'today_data.txt'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
