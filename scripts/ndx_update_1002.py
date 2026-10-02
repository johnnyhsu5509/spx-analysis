import json

D = "../docs/"


def load(n):
    return json.load(open(D + n, encoding="utf-8"))


def save(n, o):
    json.dump(o, open(D + n, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


t = load("ndx_track_record.json")
e = t["entries"][-1]
assert e["report_date"] == "2026-10-01" and e["grade"] == "pending"
e.update({
    "actual_date": "2026-10-01", "actual_pct": 0.31, "actual_dir": "flat", "grade": "hit",
    "note": "10/1 開 30,533.60 → 低 30,274.65 → 高 30,616.24 → 收 30,501.56（+0.31%）→ **flat**。預測中性 54%（預期 flat）遇 flat → **hit**，Brier 排除。\n\n"
            "【情景 B（39%）實現】收盤 30,287–30,530 之間。盤中下探 30,275（距 9/29 低 30,236 僅 39 點）後收回，下影 227 點。\n\n"
            "【當日】10Y 盤中 5.344%（2002 年以來最高）後回落收 5.24%；ISM 製造業 54.5、物價分項 77.9 偏熱；SOXX +1.35%（Micron 財報帶動）。",
})
t["entries"].append({"report_date": "2026-10-02", "basis_close": 30501.56, "basis_date": "2026-10-01",
                     "pullback_prob": 49, "bias": "中性", "actual_date": None, "actual_pct": None,
                     "actual_dir": None, "grade": "pending"})
s = t["summary"]
s.update({"as_of": "2026-10-02", "graded": 22, "hits": 10, "half": 9, "miss": 3,
          "rolling_direction_score_pct": 65.9,
          "sample_caveat": "n=22。65.9% ＝ (10 hit + 9 half×0.5 + 3 miss) / 22 = 14.5/22。"})
b = s["brier"]
b["per_entry"].append({"report_date": "2026-10-01", "p": 0.54, "outcome": "flat_excluded", "brier": None})
b["excluded_flat"] = b.get("excluded_flat", 0) + 1
b["as_of"] = "2026-10-02"
b["honest_read"] = f"mean brier 維持 **{b['mean_brier']}**（n={b['included']}）；9/24、9/30、10/1 連三筆 flat 排除——中樞整理期，Brier 樣本停止增加。"
save("ndx_track_record.json", t)

p = load("ndx_pnl_ledger.json")
assert p["trades_pending"]["report_date"] == "2026-10-01"
p["entries"].append({
    "report_date": "2026-10-01", "basis_close": 30408.5, "eval_date": "2026-10-01",
    "eval_ohlc": {"open": 30533.6, "high": 30616.24, "low": 30274.65, "close": 30501.56},
    "rule50_check": "反彈空開盤 30,533.60 已高於掛單價 30,530、但低於停損 30,730 → 開盤即成交，未觸發 prc-004。回踩多未觸發。",
    "rule51_check": "反彈空於 09:30 棒成交；10:00 棒低 30,302.4 未及 T1 30,300（差 2.4 點），11:00 棒低 30,274.7 觸及 T1 → T1 出場。成交後最高 30,615.8（13:30 棒）出現在 T1 之後，未觸及停損 30,730。",
    "trades": [
        {"name": "反彈空（中樞上沿）", "order": "limit_sell", "entry_signal": 30530, "dir": "short", "weight": 3,
         "signal_triggered": True, "filled": True, "status": "FILLED → T1 達成",
         "fill_price": 30530, "exit_price": 30300, "exit_reason": "目標① 30,300（11:00 棒低 30,274.7）",
         "pts": 230, "ret_pct": 0.7534, "weighted_bp": 2.26,
         "note": "**首筆採用 0.5 ATR 停損（cand-011 觀察）的單**。T1 達成後價格反彈到 30,615.8，距停損 30,730 仍有 114 點；若沿用 0.34 ATR 停損（約 30,666）也不會被掃——本筆不能作為 cand-011 的佐證，只是乾淨的一筆。"},
        {"name": "回踩多（9/29 低）", "order": "limit_buy", "entry_signal": 30240, "dir": "long", "weight": 3,
         "signal_triggered": False, "filled": False, "status": "NOT_TRIGGERED — 低 30,274.65 差 34.65 點",
         "pts": None, "ret_pct": None, "weighted_bp": 0.0},
    ],
    "day_weighted_bp": 2.26,
    "day_note": "反彈空 T1 +2.26bp、回踩多未觸發 → 當日 **+2.26bp**。累積 -6.21 → **-3.95bp**。",
})
sm = p["summary"]
sm.update({"as_of": "2026-10-02", "days_evaluated": 22, "trades_total": 44, "signals_triggered": 23,
           "trades_filled": 21, "trades_not_triggered": 21, "filled_win": 7, "filled_loss": 14,
           "fill_rate_pct": round(21 / 44 * 100, 1), "gap_invalidation_rate_pct": round(2 / 23 * 100, 1),
           "cumulative_weighted_bp": -3.95, "cumulative_if_intraday_checked": -6.24,
           "honest_read": "累積 -6.21 → **-3.95bp**（30 分 K 揭露口徑 -6.24bp）。10/1 中樞上沿反彈空 T1 +2.26bp。成交 21 筆 7 勝 14 敗。"})
p["trades_pending"] = {
    "report_date": "2026-10-02", "basis_close": 30501.56,
    "eval_rule": "用 2026-10-02 美股 NDX OHLC 判定；適用 rule50（prc-004）與 rule51（30 分 K 判序）。**非農於開盤前公布，跳空穿越停損者依 prc-004 判 GAP_INVALIDATED。**",
    "signal_atr14_pct": 1.303,
    "divergence_check": "【rule49】NDX 49 vs SPX 50 同為中性 → 不減半。【regime】三維內部分歧 → 視為中性，以主觀為主。",
    "trades": [
        {"name": "反彈空（雙頂 30,616／30,630）", "order": "limit_sell", "entry": 30615, "stop": 30815, "t1": 30380, "t2": 30280,
         "weight": 3, "dir": "short",
         "condition_note": "9/30 高 30,630、10/1 高 30,616 形成雙頂。停損 0.5 ATR，置於歷史盤中高 30,771 之上。RR 1.18／1.68。"},
        {"name": "回踩多（10/1 低）", "order": "limit_buy", "entry": 30300, "stop": 30060, "t1": 30580, "t2": 30700,
         "weight": 3, "dir": "long",
         "condition_note": "10/1 盤中低 30,274.7／30,302.4／30,302.7 三次測試。停損置於 9/28 低 30,081 之下（0.6 ATR）。RR 1.17／1.67。"},
    ],
    "rejected_by_rule27": [
        {"name": "突破多（歷史高 30,771 之上）", "entry": 30775, "dist_pct": 0.9, "threshold": 0.669, "reason": "超過門檻。"},
        {"name": "破位空（收盤 < 30,080）", "entry": 30080, "dist_pct": -1.38, "threshold": 0.669, "reason": "超過門檻。"},
    ],
}
save("ndx_pnl_ledger.json", p)
open("ndx_update_1002.txt", "w", encoding="utf-8").write("OK\n")
