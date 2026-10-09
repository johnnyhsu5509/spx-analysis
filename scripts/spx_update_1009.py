import json
D = "../docs/"
def ld(f): return json.load(open(D+f, encoding="utf-8"))
def sv(f, o): json.dump(o, open(D+f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

BIAS = ("中性（**AI／晶片股殺盤＋Brent 破 104，S&P 盤中跌破 10/7 低卻收在 7,763 之上 2 點；權值弱、等權強——利空換了主角，方向仍未表態**）：基準 10/8 收 7,765.36（-0.47%）。"
 "偏多：①收盤守住 10/7 低 7,763（低 7,731.26 後收回、下影 34 點、收在日內 51%）②**廣度反轉擴張**：RSP/SPY 1 日 +1.05%（近似值）、Russell 持平、Dow +0.1%＝殺在權值、非全面撤退 ③10Y 回落至 5.231%（-4.6bps）、DXY 102.11 ④VIX 15.41 <16、均線多頭排列、rule20 偏空上限 60 ⑤盤後隱含開盤 7,771（自收盤 +6 點，亞洲薄盤）。"
 "偏空：①**MACD 柱 12.21→10.18 四日來首度縮小**、收在 MA5 之下 ②連兩日收黑、盤中跌破 10/7 低 ③NDX -1.39%、晶片指數 -3.35%（ChatGPT 營收低於預期報導）④Brent 103.8（+3.6%），伊朗戰事、荷莫茲油輪遇襲，rule2 續適用 ⑤距 MA200 +7.17%。"
 "情景：A 收跌 ≤-0.3%（≤7,742）33%；B 平盤 38%；C 收漲 ≥+0.3%（≥7,789）29%。headline＝33＋38×0.5＝**52%**。**rule62：bias 中性、headline 46–54、離散度 4pp → 全日不掛**")

t = ld("track_record.json")
e = t["entries"][-1]; assert e["report_date"] == "2026-10-08"
e.update({"actual_date": "2026-10-08", "actual_pct": -0.47, "actual_dir": "down", "grade": "half",
 "grade_note": "實際 -0.47%（收 7,765.36）＝down；立場「中性」47%，**中性遇跌＝half**。Brier：p=0.47、outcome=1 → 0.2809（輸給 0.25）。跳空 -0.30% 開 7,778.45（亞盤推算 7,798.5，高估 20 點）、12:00 ET 高 7,797.79、13:00 ET 低 7,731.26（跌破 10/7 低 7,763）、收 7,765.36（收在日內 51%）。主因 AI／晶片股殺盤（ChatGPT 營收低於預期報導、NDX -1.39%、晶片指數 -3.4%）＋Brent 升至 103.8（+3.6%）；10Y 反落至 5.231%。情景 A（27%）兌現。watch point：7,763 盤中破、收盤守住（差 2 點）✗/✓；7,845 未站上 ✓；收破 7,782 ✓（情景③條件成立一半）；Russell 止跌 ✓（Python 持平）；10Y 未回 5.30% ✓（反落）；Brent 站穩 100 ✓（103.8）。**不掛的代價／收益**：long_pullback 7,775 於 09:30 首根成交（低 7,771.8）、13:00 低 7,731.3 越過停損 7,740＝-35 點；short_breakdown 收破 7,782 觸發（收盤 7,765.36 進場、隔日評價）；其餘兩張未觸發"})
t["entries"].append({"report_date": "2026-10-09", "basis_close": 7765.36, "pullback_prob": 52, "bias": BIAS,
 "actual_date": "2026-10-09(pending)", "actual_pct": None, "actual_dir": None, "grade": "pending"})
s = t["summary"]
s["graded"] += 1; s["half"] += 1
s["rolling_direction_score_pct"] = round((s["hits"] + 0.5*s["half"]) / s["graded"] * 100, 1)
b = s["brier"]; b["included"] += 1; b["as_of"] = "2026-10-09"
b["per_entry"].append({"report_date": "2026-10-08", "p": 0.47, "outcome": 1, "brier": 0.2809})
b["mean_brier"] = round(sum(x["brier"] for x in b["per_entry"]) / len(b["per_entry"]), 4)
b["note_latest"] = f"2026-10-08：中性 47% 遇 -0.47%＝down（half），Brier 0.2809。mean_brier {b['mean_brier']}（{len(b['per_entry'])} 筆）。"
n = s["graded"]; flat = b["excluded_flat"]; base = round((flat + (n-flat)*0.5)/n*100, 1)
s["always_neutral_baseline_20261009"] = f"依 rule17 並列：每天報中性基準 {base}%（{n} 筆，flat {flat}）vs 系統 {s['rolling_direction_score_pct']}%；Brier {b['mean_brier']} vs 0.25"
sv("track_record.json", t)

p = ld("pnl_ledger.json")
e = p["entries"][-1]; assert e["report_date"] == "2026-10-08"
e.update({"eval_date": "2026-10-08", "ohlc": {"o": 7778.45, "h": 7797.79, "l": 7731.26, "c": 7765.36}, "results": [], "day_weighted_bp": 0.0,
 "day_note": "**0bp（rule62 全日不掛），累積維持 -1.88bp。**對照（不入帳）：short_resist 7,845 未成交（高 7,797.79）；short_breakdown 收破 7,782 觸發（收 7,765.36，依 rule48 隔日評價，對照組不建倉）；long_pullback 7,775 於 09:30 首根成交（開 7,778.45、低 7,771.8），30 分 K 序列：13:00 ET 低 7,731.3 越過停損 7,740＝**-35 點停損**（收盤 7,765.36）；breakout_long 7,846 未觸發。rule62 第四度擋掉停損單（10/5、10/6 空單、10/7、10/8 多單）。discretionary_log 不新增"})
p["entries"].append({"report_date": "2026-10-09", "eval_date": "pending(2026-10-09 US close)", "basis_close": 7765.36,
 "thresholds": {"rule27_pct": 0.469, "rule31_up_pct": 0.557, "rule31_down_pct": 0.139,
  "exec_band": "7,729–7,802 (rule27)｜上行掛單<=7,809｜下行掛單>=7,755 (rule31)",
  "note": "ATR14（Wilder）67.44（0.868%）、近5日均振幅 0.694% → 預期振幅 0.781%，rule27 門檻 0.469%；rule61 停損下限 0.5×ATR＝33.7 點"},
 "trades_pending": [],
 "rule27_rejected": [
  {"name": "short_resist", "order": "limit_sell", "entry": 7795, "stop": 7830, "t1": 7745, "t2": 7731, "dist_pct": 0.38, "threshold_pct": 0.469, "rr_t1": 1.43, "weight": 0,
   "reason": "rule62 全日不掛。錨 10/8 高 7,797.79 與 MA5 隔日預估 7,795，停損放 10/7 高 7,807 之外並滿足 0.5×ATR（35 點）；RR 1.43 → 若有 lean 須減半"},
  {"name": "short_breakdown", "order": "sell_stop_close_confirm", "entry": 7731, "stop": 7770, "t1": 7700, "t2": 7667, "dist_pct": -0.44, "threshold_pct": 0.469, "weight": 0,
   "reason": "rule62 全日不掛；收破 7,731（10/8 低）＝向上筆結束、回測中樞上沿 7,700"},
  {"name": "long_pullback", "order": "limit_buy", "entry": 7735, "stop": 7695, "t1": 7790, "t2": 7807, "dist_pct": -0.39, "threshold_pct": 0.469, "rr_t1": 1.38, "weight": 0,
   "reason": "rule62 全日不掛；錨 10/8 低 7,731（rule8 首觸即掛），停損放 MA20 7,697 之下（risk 40）；超出 rule31 下行門檻（≥7,755）、RR 1.38 → 若有 lean 須減半"},
  {"name": "breakout_long", "order": "buy_stop", "entry": 7808, "dist_pct": 0.55, "threshold_pct": 0.469, "weight": 0,
   "reason": "rule27 超標（0.55%）；rule3：MACD 柱縮小、量能為初值 → 不成立；rule62"}],
 "structure_note": "**今日無 edge，不掛（rule62）**：bias 中性、headline 52 落在 46–54、情景離散度 4pp <10pp，三條全中（連 5 日）。四種策略照列供對照，weight 皆 0"})
ps = p["summary"]; ps["as_of"] = "2026-10-09"; ps["days_evaluated"] += 1
ps["honest_read"] = "10/8 rule62 全日不掛，**0bp，累積維持 -1.88bp**（58 日）。對照：long_pullback 7,775 會在首根 30 分 K 成交、被 13:00 低 7,731.3 掃停損（-35 點）——rule62 連四日擋掉停損單（10/5、10/6 空單、10/7、10/8 多單）；short_breakdown 收破 7,782 觸發（對照組）。10/9 第五度三條全中、不掛。"
sv("pnl_ledger.json", p)
open("spx_update_1009.txt","w",encoding="utf-8").write(f"ok roll={s['rolling_direction_score_pct']} base={base} brier={b['mean_brier']} n={n} days={ps['days_evaluated']}")
