import json

D = "../docs/"


def load(n):
    return json.load(open(D + n, encoding="utf-8"))


def save(n, o):
    json.dump(o, open(D + n, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


t = load("ndx_track_record.json")
e = t["entries"][-1]
assert e["report_date"] == "2026-09-30" and e["grade"] == "pending"
e.update({
    "actual_date": "2026-09-30", "actual_pct": 0.23, "actual_dir": "flat", "grade": "hit",
    "note": "9/30 開 30,421.68 → 高 30,630.45 → 低＝收 30,408.50（+0.23%）→ **flat**。預測中性 54%（預期 flat）遇 flat → **hit**，Brier 排除。\n\n"
            "【情景 B（40%）實現】收盤 30,218–30,461 之間。盤中最高 +0.96%，**季底最後 30 分鐘由 30,557.8 殺到 30,410.7**，收在全日最低。\n\n"
            "【當日數據】8 月 PCE 3.4%（預期 3.7%）、核心 3.0%（預期 3.3%）皆偏軟，但 10Y 仍升至 5.29%、30Y 5.63%（2002 年以來最高收盤）。",
})
t["entries"].append({"report_date": "2026-10-01", "basis_close": 30408.5, "basis_date": "2026-09-30",
                     "pullback_prob": 54, "bias": "中性", "actual_date": None, "actual_pct": None,
                     "actual_dir": None, "grade": "pending"})
s = t["summary"]
s.update({"as_of": "2026-10-01", "graded": 21, "hits": 9, "half": 9, "miss": 3,
          "rolling_direction_score_pct": 64.3,
          "sample_caveat": "n=21。64.3% ＝ (9 hit + 9 half×0.5 + 3 miss) / 21 = 13.5/21。"})
b = s["brier"]
b["per_entry"].append({"report_date": "2026-09-30", "p": 0.54, "outcome": "flat_excluded", "brier": None})
b["excluded_flat"] = b.get("excluded_flat", 0) + 1
b["as_of"] = "2026-10-01"
b["honest_read"] = f"mean brier 維持 **{b['mean_brier']}**（n={b['included']}）；9/24、9/30 連兩筆 flat 排除。"
save("ndx_track_record.json", t)

p = load("ndx_pnl_ledger.json")
assert p["trades_pending"]["report_date"] == "2026-09-30"
p["entries"].append({
    "report_date": "2026-09-30", "basis_close": 30339.33, "eval_date": "2026-09-30",
    "eval_ohlc": {"open": 30421.68, "high": 30630.45, "low": 30408.5, "close": 30408.5},
    "rule50_check": "反彈空開盤 30,421.68 < 停損 30,620 → 未跳空穿越，正常判定。回踩多未觸發。",
    "rule51_check": "反彈空於 09:30 棒（高 30,562.9）成交 30,480；成交後最低 30,499.5（13:00 棒）未及 T1 30,240；11:30 棒高 30,628.5 觸及停損 30,620 → 停損出場。",
    "trades": [
        {"name": "反彈空（9/28 高）", "order": "limit_sell", "entry_signal": 30480, "dir": "short", "weight": 3,
         "signal_triggered": True, "filled": True, "status": "FILLED → 停損出場",
         "fill_price": 30480, "exit_price": 30620, "exit_reason": "停損 30,620（11:30 棒高 30,628.5，穿越 8.5 點）",
         "pts": -140, "ret_pct": -0.4593, "weighted_bp": -1.38,
         "note": "**停損只有 0.34 ATR，被穿越 8.5 點後收盤跌到 30,408.5**——若停損放在 0.5 ATR（約 30,680）之外，這筆收盤平倉為 +71.5 點。SPX 系統同日也記下相同現象（0.35 ATR 停損被掃）。"},
        {"name": "回踩多（9/29 低）", "order": "limit_buy", "entry_signal": 30240, "dir": "long", "weight": 2,
         "signal_triggered": False, "filled": False, "status": "NOT_TRIGGERED — 全日低 30,408.5",
         "pts": None, "ret_pct": None, "weighted_bp": 0.0},
    ],
    "day_weighted_bp": -1.38,
    "day_note": "反彈空停損 -1.38bp、回踩多未觸發 → 當日 **-1.38bp**。累積 -4.83 → **-6.21bp**。",
})
p.setdefault("candidate_rules_pnl", []).append({
    "id": "cand-011", "raised_on": "2026-10-01",
    "observation": "停損距離 < 0.5 ATR 的限價單易被盤中雜訊掃掉。9/30 反彈空停損 0.34 ATR，被穿越 8.5 點後收盤反向 211 點；9/22 反壓空停損 0.41 ATR 則撐過（差 49 點）。",
    "hypothesis": "限價單停損距離下限設為 0.5 ATR，可降低被掃比例而不顯著降低 RR。",
    "verification_plan": "回溯本帳所有限價單成交紀錄，按停損/ATR 分檔統計停損出場率與收盤反向比例。",
    "spx_note": "SPX 系統同日提出 rule60 候補（同一現象），兩套各自驗證，不互相引用結論。",
    "why_not_now": "兩個樣本不足以立案。"})
sm = p["summary"]
sm.update({"as_of": "2026-10-01", "days_evaluated": 21, "trades_total": 42, "signals_triggered": 22,
           "trades_filled": 20, "trades_not_triggered": 20, "filled_loss": 14,
           "fill_rate_pct": round(20 / 42 * 100, 1), "gap_invalidation_rate_pct": round(2 / 22 * 100, 1),
           "cumulative_weighted_bp": -6.21, "cumulative_if_intraday_checked": -8.50,
           "honest_read": "累積 -4.83 → **-6.21bp**（30 分 K 揭露口徑 -8.50bp）。9/30 反彈空 0.34 ATR 停損被掃 -1.38bp，收盤其實反向有利；立 cand-011。成交 20 筆 6 勝 14 敗。"})
p["trades_pending"] = {
    "report_date": "2026-10-01", "basis_close": 30408.5,
    "eval_rule": "用 2026-10-01 美股 NDX OHLC 判定；適用 rule50（prc-004）與 rule51（30 分 K 判序）。",
    "signal_atr14_pct": 1.314,
    "divergence_check": "【rule49】NDX 54 vs SPX 50 同側（皆中性）→ 不減半。【regime】三維內部分歧（VXN +4.3 vs 趨勢 -3.7、MA20 -3.6）→ 視為中性，以主觀為主、保守看待。",
    "trades": [
        {"name": "反彈空（中樞上沿）", "order": "limit_sell", "entry": 30530, "stop": 30730, "t1": 30300, "t2": 30210,
         "weight": 3, "dir": "short",
         "condition_note": "9/24 高 30,529＝9/23–9/29 中樞上沿；9/30 盤中突破後季底收回。停損 0.5 ATR（200 點），置於 9/23 開盤高 30,706 之上（cand-011 觀察：不再用 < 0.5 ATR 的停損）。RR 1.15／1.60。"},
        {"name": "回踩多（9/29 低）", "order": "limit_buy", "entry": 30240, "stop": 30040, "t1": 30480, "t2": 30630,
         "weight": 3, "dir": "long",
         "condition_note": "9/29 盤中雙低 30,236／30,241。停損 9/28 低 30,081 之下、0.5 ATR。RR 1.20／1.95。"},
    ],
    "rejected_by_rule27": [
        {"name": "反彈空（9/30 高 30,630）", "entry": 30630, "dist_pct": 0.73, "threshold": 0.669, "reason": "超過門檻。"},
        {"name": "回踩多（9/28 低 30,081）", "entry": 30090, "dist_pct": -1.05, "threshold": 0.669, "reason": "超過門檻。"},
    ],
}
save("ndx_pnl_ledger.json", p)
open("ndx_update_1001.txt", "w", encoding="utf-8").write("OK\n")
