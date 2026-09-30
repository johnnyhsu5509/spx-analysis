import json

D = "../docs/"


def load(n):
    return json.load(open(D + n, encoding="utf-8"))


def save(n, o):
    json.dump(o, open(D + n, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


t = load("ndx_track_record.json")
e = t["entries"][-1]
assert e["report_date"] == "2026-09-24" and e["grade"] == "pending"
e.update({
    "actual_date": "2026-09-24", "actual_pct": 0.03, "actual_dir": "flat", "grade": "half",
    "note": "9/24 開 30,225.19 → 高 30,529.35 → 低 30,204.16 → 收 30,478.86（+0.03%）→ **flat**。預測中性偏空 59% 遇 flat → **half**，Brier 排除。\n\n"
            "【情景 B（40%）實現】收盤落在 30,348–30,592。開盤跳空 -0.8% 後盤中收復，川習峰會當日。\n\n"
            "【峰會結果（已查證，9/23–25）】象徵大於實質：成立 AI 對話機制、貿易休戰延至 1/10；晶片出口管制未上議程。",
})
t["entries"].append({"report_date": "2026-09-30", "basis_close": 30339.33, "basis_date": "2026-09-29",
                     "pullback_prob": 54, "bias": "中性", "actual_date": None, "actual_pct": None,
                     "actual_dir": None, "grade": "pending"})
s = t["summary"]
s.update({"as_of": "2026-09-30", "graded": 20, "hits": 8, "half": 9, "miss": 3,
          "rolling_direction_score_pct": 62.5,
          "sample_caveat": "n=20。62.5% ＝ (8 hit + 9 half×0.5 + 3 miss) / 20 = 12.5/20。"})
s["gap_days"] = sorted(set(s["gap_days"] + ["2026-09-25", "2026-09-28"]))
b = s["brier"]
b["per_entry"].append({"report_date": "2026-09-24", "p": 0.59, "outcome": "flat_excluded", "brier": None})
b["excluded_flat"] = b.get("excluded_flat", 0) + 1
b["as_of"] = "2026-09-30"
b["honest_read"] = f"mean brier 維持 **{b['mean_brier']}**（n={b['included']}）；9/24 flat 排除。連三筆 half（9/22、9/23、9/24）。"
save("ndx_track_record.json", t)

p = load("ndx_pnl_ledger.json")
tp = p["trades_pending"]
assert tp["report_date"] == "2026-09-24"
op = p["open_positions"][0]
p["entries"].append({
    "report_date": "2026-09-24", "basis_close": 30470.29, "eval_date": "2026-09-24",
    "eval_ohlc": {"open": 30225.19, "high": 30529.35, "low": 30204.16, "close": 30478.86},
    "rule50_check": "雙底接多：開盤 30,225.19 低於進場 30,360、但高於停損 30,180 → 未觸發 prc-004，正常成交。反彈空未觸發。",
    "rule51_check": "雙底接多於 09:30 首棒成交（開盤即低於掛單價）；全日低 30,204.16 未及停損 30,180，高 30,529.35 未及 T1 30,590 → 收盤平倉。",
    "closed_positions": [{
        "name": "破位空（9/23 成交）", "order": "sell_stop_close_confirm", "dir": "short", "weight": 3,
        "fill_price": 30470.29, "t1": op["t1"], "t2": op["t2"], "stop": op["stop"],
        "exit_price": 30478.86, "exit_reason": f"收盤平倉（低 30,204.16 距浮動 T1 {op['t1']:,} 僅 {round(30204.16 - op['t1'], 2)} 點；高 30,529.35 未及停損）",
        "pts": -8.57, "ret_pct": -0.0281, "weighted_bp": -0.08}],
    "trades": [
        {"name": "反彈空（舊歷史高轉壓力）", "order": "limit_sell", "entry_signal": 30661, "dir": "short", "weight": 4,
         "signal_triggered": False, "filled": False, "status": "NOT_TRIGGERED — 高 30,529.35 未及 30,661",
         "pts": None, "ret_pct": None, "weighted_bp": 0.0},
        {"name": "回踩多（9/23 盤中雙底）", "order": "limit_buy", "entry_signal": 30360, "dir": "long", "weight": 3,
         "signal_triggered": True, "filled": True, "status": "FILLED → 收盤平倉",
         "fill_price": 30360, "exit_price": 30478.86, "exit_reason": "收盤平倉（T1 30,590、停損 30,180 皆未觸及）",
         "pts": 118.86, "ret_pct": 0.3915, "weighted_bp": 1.17,
         "fill_note": "開盤 30,225.19 已低於掛單價，實務上會以開盤價附近成交（約 +253 點）；帳本依慣例以掛單價計，屬保守。"},
    ],
    "day_weighted_bp": 1.09,
    "day_note": "雙底接多 +1.17bp、留倉破位空收盤平倉 -0.08bp、反彈空未觸發 → 當日 **+1.09bp**。累積 -5.92 → **-4.83bp**。",
})
p["open_positions"] = []
p["gap_note_2026_09_25"] = {"date": "2026-09-25", "status": "GAP DAY", "actual": "NDX 收 30,608.13（+0.42%），高 30,667.56 回測舊歷史高 30,661 失敗", "note": "不計入統計。"}
p["gap_note_2026_09_28"] = {"date": "2026-09-28", "status": "GAP DAY", "actual": "NDX 收 30,276.81（-1.08%），低 30,081.06", "note": "不計入統計。"}
sm = p["summary"]
sm.update({"as_of": "2026-09-30", "days_evaluated": 20, "trades_total": 40, "signals_triggered": 21,
           "trades_filled": 19, "trades_not_triggered": 19, "filled_win": 6, "filled_loss": 13,
           "fill_rate_pct": round(19 / 40 * 100, 1), "gap_invalidation_rate_pct": round(2 / 21 * 100, 1),
           "cumulative_weighted_bp": -4.83, "cumulative_if_intraday_checked": -7.12, "open_positions": 0,
           "gap_days": sorted(set(sm["gap_days"] + ["2026-09-25", "2026-09-28"])),
           "honest_read": "累積 -5.92 → **-4.83bp**（30 分 K 揭露口徑 -7.12bp）。9/24 雙底接多 +1.17bp；破位空浮動 T1 差 34 點未達，收盤平倉 -0.08bp。成交 19 筆 6 勝 13 敗。"})
p["trades_pending"] = {
    "report_date": "2026-09-30", "basis_close": 30339.33,
    "eval_rule": "用 2026-09-30 美股 NDX OHLC 判定；適用 rule50（prc-004）與 rule51（30 分 K 判序）。",
    "signal_atr14_pct": 1.339,
    "divergence_check": "【rule49】NDX 54 vs SPX 59 同側 → 不因跨系統減半。【regime】主觀 54 偏空側 vs 客觀 -1.0pp 偏多側 → 弱分歧，倉位減半（反彈空 4→3%、回踩多 4→2%）。",
    "trades": [
        {"name": "反彈空（9/28 高）", "order": "limit_sell", "entry": 30480, "stop": 30620, "t1": 30240, "t2": 30090,
         "weight": 3, "dir": "short",
         "condition_note": "9/23 起高點連續下移（30,706 → 30,668 → 30,480 → 30,430）；掛 9/28 高 30,480。停損置於 9/24 高 30,529 與 9/25 收 30,608 之上，140 點＝0.34 ATR。RR 1.71／2.79。"},
        {"name": "回踩多（9/29 低）", "order": "limit_buy", "entry": 30240, "stop": 30060, "t1": 30430, "t2": 30529,
         "weight": 2, "dir": "long",
         "condition_note": "9/29 盤中低 30,236／30,241（12:30、13:30 棒）。停損 9/28 低 30,081 之下。RR 1.06／1.61，T1 風報比偏低，倉位最小。"},
    ],
    "rejected_by_rule27": [
        {"name": "回踩多（9/28 低 30,081）", "entry": 30090, "dist_pct": -0.82, "threshold": 0.702, "reason": "超過門檻。"},
        {"name": "破位空（收盤 < 30,080）", "entry": 30080, "dist_pct": -0.86, "threshold": 0.702, "reason": "超過門檻。"},
    ],
}
save("ndx_pnl_ledger.json", p)
open("ndx_update_0930.txt", "w", encoding="utf-8").write("OK\n")
