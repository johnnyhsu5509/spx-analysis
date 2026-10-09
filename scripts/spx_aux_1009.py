import json, yfinance as yf, pandas as pd, numpy as np
def dl(t, p="400d", i="1d"):
    d = yf.download(t, period=p, interval=i, progress=False, auto_adjust=False)
    if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
    return d.dropna(subset=["Close"])
s = dl("^GSPC"); out = {"last_date": str(s.index[-1].date())}
h,l,c = s["High"], s["Low"], s["Close"]; pc = c.shift(1)
tr = pd.concat([h-l,(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
atr = tr.ewm(alpha=1/14, adjust=False).mean()
px = float(c.iloc[-1]); A = float(atr.iloc[-1])
out["atr14_wilder"] = round(A,2); out["atr_pct"] = round(A/px*100,3)
rng5 = float(((h-l)/c*100).tail(5).mean()); out["range5_pct"] = round(rng5,3)
em = (A/px*100 + rng5)/2; out["expected_move_pct"] = round(em,3); out["rule27_pct"] = round(em*0.6,3)
out["exec_band"] = [round(px*(1-em*0.6/100)), round(px*(1+em*0.6/100))]
up = ((h-pc)/pc*100).tail(5); dn = ((pc-l)/pc*100).tail(5)
out["rule31_up_pct"] = round(float(up.mean()),3); out["rule31_down_pct"] = round(float(dn.mean()),3)
d = c.diff(); g = d.clip(lower=0).ewm(alpha=1/14,adjust=False).mean(); ls = (-d.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
out["rsi_wilder"] = round(float(100-100/(1+g.iloc[-1]/ls.iloc[-1])),2)
ll = l.rolling(9).min(); hh = h.rolling(9).max(); rsv = (c-ll)/(hh-ll)*100
k = rsv.ewm(alpha=1/3,adjust=False).mean(); dd = k.ewm(alpha=1/3,adjust=False).mean()
out["kd9"] = [round(float(k.iloc[-1]),1), round(float(dd.iloc[-1]),1)]
for n in (5,20,50,200):
    m = c.rolling(n).mean(); mv = m.diff().tail(5)
    out[f"ma{n}"] = round(float(m.iloc[-1]),2); out[f"ma{n}_d3"] = [round(float(x),1) for x in m.diff().tail(3)]
    out[f"ma{n}_next"] = round(float(m.iloc[-1]+mv.mean()),1)
out["dev_ma200_pct"] = round((px/out["ma200"]-1)*100,2); out["dev_ma20_pct"] = round((px/out["ma20"]-1)*100,2)
o,hi,lo = float(s["Open"].iloc[-1]), float(h.iloc[-1]), float(l.iloc[-1]); p0=float(c.iloc[-2])
out["candle"] = {"gap_pct": round((o-p0)/p0*100,3), "close_pos_pct": round((px-lo)/(hi-lo)*100,1),
  "upper_wick": round(hi-max(o,px),1), "lower_wick": round(min(o,px)-lo,1), "body": round(px-o,1), "range_pct": round((hi-lo)/px*100,3)}
out["chg_last5"] = [round(float(x),2) for x in (c.pct_change()*100).tail(5)]
out["vol_last6"] = [int(x) for x in s["Volume"].tail(6)]
m = dl("^GSPC","10d","30m")
idx = m.index.tz_convert("America/New_York")
day = m[[str(x.date())==out["last_date"] for x in idx]]
out["bars30_last"] = [[str(i.tz_convert("America/New_York").time())[:5], round(float(r.Open),1), round(float(r.High),1), round(float(r.Low),1), round(float(r.Close),1)] for i,r in day.iterrows()]
for t,k2 in [("^TNX","tnx"),("BZ=F","brent"),("CL=F","wti"),("DX-Y.NYB","dxy"),("^RUT","rut"),("SOXX","soxx"),("^NDX","ndx")]:
    x = dl(t,"15d")["Close"]; out[k2] = [round(float(x.iloc[-2]),3), round(float(x.iloc[-1]),3), str(x.index[-1].date())]
json.dump(out, open("spx_aux_1009.txt","w",encoding="utf-8"), ensure_ascii=False, indent=1)
