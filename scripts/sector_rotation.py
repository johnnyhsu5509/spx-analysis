import yfinance as yf, pandas as pd
from datetime import datetime

groups = {
 "大族群": ["SMH","XLK","QQQ","VUG","IWM","XLF","XLE","XLV","XLI","XLP","XLU","VTV"],
 "AI鏈": ["NVDA","AMD","MU","AVGO","MRVL","TSM","COHR","LITE","FN","VRT","VST","CEG","ETN","PWR","SNPS","CDNS"],
 "Mag7": ["AAPL","MSFT","GOOGL","AMZN","META","NVDA","TSLA"],
}
nm = {"SMH":"半導","XLK":"科技","QQQ":"那指","VUG":"成長","IWM":"小型","XLF":"金融","XLE":"能源","XLV":"健康","XLI":"工業","XLP":"必需","XLU":"公用","VTV":"價值",
 "NVDA":"GPU","AMD":"GPU","MU":"記憶體","AVGO":"ASIC","MRVL":"ASIC","TSM":"代工","COHR":"光通訊","LITE":"光通訊","FN":"光通訊","VRT":"電力","VST":"電力","CEG":"電力","ETN":"電力","PWR":"電力","SNPS":"EDA","CDNS":"EDA",
 "AAPL":"Apple","MSFT":"MSFT","GOOGL":"Google","AMZN":"AMZN","META":"META","TSLA":"TSLA"}
allt = sorted(set(t for v in groups.values() for t in v))
close = yf.download(allt, start="2025-12-15", end="2026-07-02", progress=False, auto_adjust=True)["Close"]
if isinstance(close, pd.Series): close = close.to_frame()
asof = close.index[-1].date()

def calc(t):
    s = close[t].dropna()
    if len(s)<64: return None
    p=s.iloc[-1]
    r5=(p/s.iloc[-6]-1)*100; r21=(p/s.iloc[-22]-1)*100; r63=(p/s.iloc[-64]-1)*100
    pace5=r5/5; pace63=r63/63
    fl="HOT" if (pace5>pace63*1.3 and r5>0) else ("COOL" if pace5<pace63*0.4 else "")
    return r5,r21,r63,fl

def cell(v):
    c = "#00e676" if v>0 else ("#ff5252" if v<0 else "#aaa")
    return f'<td style="color:{c};text-align:right">{v:+.1f}</td>'

def rows(ts):
    data=[]
    for t in ts:
        c=calc(t)
        if c: data.append((t,)+c)
    data.sort(key=lambda x:-x[2])
    h=""
    for t,r5,r21,r63,fl in data:
        flhtml = '<span style="color:#ff7043">🔥</span>' if fl=="HOT" else ('<span style="color:#4fc3f7">🧊</span>' if fl=="COOL" else "")
        h+=f'<tr><td style="color:#e0e0e0">{t} <span style="color:#666;font-size:11px">{nm.get(t,"")}</span></td>{cell(r5)}{cell(r21)}{cell(r63)}<td style="text-align:center">{flhtml}</td></tr>'
    return h

def r(t,n):
    s=close[t].dropna(); return (s.iloc[-1]/s.iloc[-1-n]-1)*100
g_v = "成長領先" if r('VUG',21)>r('VTV',21) else "價值領先"
sm_q = "小型領先" if r('IWM',21)>r('QQQ',21) else "大型/科技領先"
ro = "RISK-ON" if r('XLK',21)>r('XLP',21) else "RISK-OFF"

th='<th style="text-align:right;color:#888;font-weight:500;padding:4px 8px">{}</th>'
head=f'<tr><th style="text-align:left;color:#888;font-weight:500;padding:4px 8px">標的</th>{th.format("1週")}{th.format("1月")}{th.format("3月")}<th style="color:#888">趨勢</th></tr>'

html=f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>族群輪動地圖 {asof}</title></head>
<body style="margin:0;background:#0a0a0a;color:#e0e0e0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px">
<div style="max-width:760px;margin:0 auto">
<div style="border-bottom:1px solid #1de9b6;padding-bottom:12px;margin-bottom:20px">
<div style="color:#1de9b6;font-size:13px;letter-spacing:2px">SECTOR ROTATION MAP</div>
<h1 style="margin:6px 0;font-size:26px">🗺️ 族群輪動地圖</h1>
<div style="color:#888;font-size:13px">資料截至 {asof}　|　🔥加速　🧊降溫</div></div>

<div style="background:#141414;border-left:3px solid #ffca28;padding:14px 16px;margin-bottom:20px;border-radius:4px">
<b style="color:#ffca28">一句話</b><br><span style="color:#ccc;font-size:14px;line-height:1.6">
風格三盞燈：{g_v} / {sm_q} / <b style="color:{'#00e676' if ro=='RISK-ON' else '#ff5252'}">{ro}</b>。
看這三盞與下表判斷錢往哪流；交易倉跟著熱區、避開降溫的拋物線頂端。</span></div>

<h2 style="font-size:16px;color:#1de9b6;border-bottom:1px solid #222;padding-bottom:6px">📊 大族群（依1月排序）</h2>
<table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:24px">{head}{rows(groups['大族群'])}</table>

<h2 style="font-size:16px;color:#1de9b6;border-bottom:1px solid #222;padding-bottom:6px">🔬 AI 鏈內細分</h2>
<table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:24px">{head}{rows(groups['AI鏈'])}</table>

<h2 style="font-size:16px;color:#1de9b6;border-bottom:1px solid #222;padding-bottom:6px">👑 Mag7</h2>
<table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:24px">{head}{rows(groups['Mag7'])}</table>

<div style="background:#141414;padding:14px 16px;border-radius:4px;font-size:13px;color:#999;line-height:1.7">
<b style="color:#ccc">讀法</b>：① 看「1月」欄抓資金搬家方向（比1週可靠）② 3月翻倍卻🧊降溫＝拋物線頂端，別追 ③ 三盞燈全防禦＝risk-off，交易倉轉輕 ④ 輪動看趨勢，每週讀一張。<br>
<span style="color:#666">本分析僅供學習參考，不構成投資建議。</span></div>
</div></body></html>"""

open("../docs/rotation.html","w",encoding="utf-8").write(html)
print("done",asof)
