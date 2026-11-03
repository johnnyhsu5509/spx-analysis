"""NDX 舊日子沒有 ndx_today_data.txt 時，從實跑後的帳本反推 ndx_daily_mech.py 需要的欄位。"""
import json, os, sys
b, a = sys.argv[1], sys.argv[2]
pl = json.load(open(os.path.join(a, 'ndx_pnl_ledger.json'), encoding='utf-8'))
e, tp = pl['entries'][-1], pl['trades_pending']
o = e['eval_ohlc']
td = {'symbol': 'NDX', 'trade_date': e['eval_date'], 'open': o['open'], 'high': o['high'], 'low': o['low'], 'close': o['close'],
      'prev_close': e['basis_close'],
      'amplitude': {'as_of': e['eval_date'], 'amp_forecast_pct': tp['signal_A_pct'], 'amp_forecast_pts': tp['signal_A_pts']}}
json.dump(td, open(os.path.join(b, 'ndx_today_data.txt'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
