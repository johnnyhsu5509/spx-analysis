import json, yfinance as yf, pandas as pd, numpy as np

def dl(t, p="300d"):
    d = yf.download(t, period=p, progress=False, auto_adjust=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    return d.dropna(subset=["Close"])

out = {}
for nm, tk in [("tnx","^TNX"),("dxy","DX-Y.NYB")]:
    try:
        d = dl(tk, "60d")
        out[nm+"_last"] = round(float(d["Close"].iloc[-1]),3)
        out[nm+"_prev"] = round(float(d["Close"].iloc[-2]),3)
        out[nm+"_chg"] = round(float(d["Close"].iloc[-1]-d["Close"].iloc[-2]),3)
        out[nm+"_chg_pct"] = round(float(d["Close"].pct_change().iloc[-1]*100),2)
        out[nm+"_date"] = str(d.index[-1].date())
    except Exception as e:
        out[nm+"_err"] = str(e)

ndx = dl("^NDX")
c = ndx["Close"]
d1 = c.diff()
# next 5 bars that will drop out of the 14d RSI window
rows=[]
for i in range(15, 10, -1):
    rows.append({"date": str(d1.index[-i].date()), "chg_pts": round(float(d1.iloc[-i]),2)})
out["next_dropout_bars"] = rows
out["last5_bars"] = [{"date": str(d1.index[-i].date()), "chg_pts": round(float(d1.iloc[-i]),2)} for i in range(5,0,-1)]

# consecutive down days / distance metrics
px = float(c.iloc[-1])
for k,v in {"ma5":29808.60,"ma20":29049.23,"ma50":29306.31,"ma200":26793.41,
            "fib618":29392.28,"fib50":28969.12,"fib786":29994.76,
            "gap_lo":29594.89,"gap_hi":29995.38}.items():
    out["dist_"+k+"_pct"] = round((px-v)/v*100,2)

# QQQ/SOXX/QQQE 20d vol ratio
for nm, tk in [("soxx","SOXX"),("qqqe","QQQE")]:
    d = dl(tk)
    out[nm+"_vs_ma5_pct"] = round(float(d["Close"].iloc[-1]/d["Close"].rolling(5).mean().iloc[-1]-1)*100,2)

# VXN history
v = dl("^VXN","60d")["Close"]
out["vxn_last5"] = [round(float(x),2) for x in v.tail(5)]
with open("ndx_aux_0819.txt","w",encoding="utf-8") as f:
    json.dump(out,f,indent=2,ensure_ascii=False)
print("OK")
