import json

D = "../docs/"


def load(n):
    return json.load(open(D + n, encoding="utf-8"))


def save(n, o):
    json.dump(o, open(D + n, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


t = load("ndx_track_record.json")
e = t["entries"][-1]
assert e["report_date"] == "2026-09-23" and e["grade"] == "pending"
e.update({
    "actual_date": "2026-09-23", "actual_pct": -0.85, "actual_dir": "down", "grade": "half",
    "note": "9/23 開 30,706.23（＝全日高）→ 低 30,353.88 → 收 30,470.29（-0.85%，以官方 9/22 收盤 30,732.40 計；Yahoo 9/22 列被撤回、30 分 K 補值為 30,728.40）→ **down**。預測中性 52% 遇 down → **half**。Brier (0.52-1)² = 0.2304。\n\n"
            "【情景 C（33%）實現】收盤 < 30,600 成立，並跌回舊歷史收盤高 30,661 之下。\n\n"
            "【病因】PMI 偏熱 + Fed 理事 Barr 稱需再升息 → 10Y 4.963 → 5.114（盤中 5.135%，2007 年以來最高）。**這是已發生的數據驅動衝擊，前一日新聞檢查時尚未存在，不構成漏查。**",
})
t["entries"].append({"report_date": "2026-09-24", "basis_close": 30470.29, "basis_date": "2026-09-23",
                     "pullback_prob": 59, "bias": "中性偏空", "actual_date": None, "actual_pct": None,
                     "actual_dir": None, "grade": "pending"})
s = t["summary"]
s.update({"as_of": "2026-09-24", "graded": 19, "hits": 8, "half": 8, "miss": 3,
          "rolling_direction_score_pct": 63.2,
          "sample_caveat": "n=19。63.2% ＝ (8 hit + 8 half×0.5 + 3 miss) / 19 = 12/19。"})
b = s["brier"]
b["per_entry"].append({"report_date": "2026-09-23", "p": 0.52, "outcome": 1, "brier": 0.2304})
inc = [x for x in b["per_entry"] if x["brier"] is not None]
mean = round(sum(x["brier"] for x in inc) / len(inc), 4)
b.update({"as_of": "2026-09-24", "included": len(inc), "mean_brier": mean,
          "honest_read": f"mean brier 0.2403 → **{mean}**（n={len(inc)}）。連兩日報中性（51、52）連兩日拿 half：方向一次上、一次下，中性判斷本身沒錯，但也沒有提供資訊。"})
save("ndx_track_record.json", t)

p = load("ndx_pnl_ledger.json")
tp = p["trades_pending"]
assert tp["report_date"] == "2026-09-23"
atr_pts = round(30470.29 * 1.231 / 100, 2)
ft = {"t1": round(30470.29 - 0.8 * atr_pts, 2), "t2": round(30470.29 - 1.6 * atr_pts, 2), "stop": round(30470.29 + 0.8 * atr_pts, 2)}
p["entries"].append({
    "report_date": "2026-09-23", "basis_close": 30732.4, "eval_date": "2026-09-23",
    "eval_ohlc": {"open": 30706.23, "high": 30706.23, "low": 30353.88, "close": 30470.29},
    "rule50_check": "回踩多開盤 30,706.23 > 停損 30,480 → 未跳空穿越；突破多未觸發；破位空為收盤確認單不適用。",
    "rule51_check": "首次以 prc-006 判序。回踩多：09:30 棒（低 30,544.3）成交 30,661；該棒未觸及停損 30,480，10:00 棒低 30,354.3 才觸及停損 → 先成交後停損，判定清楚。全日高即開盤 30,706.23，T1 30,960 未觸及。",
    "trades": [
        {"name": "回踩多", "order": "limit_buy", "entry_signal": 30661, "dir": "long", "weight": 4,
         "signal_triggered": True, "filled": True, "status": "FILLED → 停損出場",
         "fill_price": 30661, "exit_price": 30480, "exit_reason": "停損 30,480（10:00 棒低 30,354.3）",
         "pts": -181, "ret_pct": -0.5903, "weighted_bp": -2.36,
         "note": "舊歷史收盤高作為支撐只撐了 30 分鐘。支撐失效的原因是利率衝擊，不是技術面。"},
        {"name": "突破多", "order": "buy_stop", "entry_signal": 30775, "dir": "long", "weight": 3,
         "signal_triggered": False, "filled": False, "status": "NOT_TRIGGERED — 全日高 30,706.23 未及 30,775",
         "pts": None, "ret_pct": None, "weighted_bp": 0.0},
        {"name": "破位空", "order": "sell_stop_close_confirm", "entry_signal": 30590, "dir": "short", "weight": 3,
         "signal_triggered": True, "filled": True, "status": "FILLED → OPEN_POSITION（prc-001 留倉至次一交易日）",
         "fill_price": 30470.29, "fill_note": "收盤 30,470.29 < 30,590，rule12 收盤確認成立。", "slippage_pts": 119.71,
         "floating_targets": {"atr_source": "訊號日 2026-09-22 的 ATR14 = 1.231%", "atr_pts": atr_pts, **ft,
                              "note": "T1 = 成交價 − 0.8 ATR、T2 = 成交價 − 1.6 ATR、停損 = 成交價 + 0.8 ATR。RR 恆為 1.00／2.00。"},
         "gap_check": "通過（浮動 T1 恆距成交價 0.8 ATR）。", "pts": None, "ret_pct": None, "weighted_bp": None},
    ],
    "day_weighted_bp": -2.36,
    "day_note": "回踩多停損 -2.36bp、突破多未觸發、破位空成交留倉 → 當日 **-2.36bp**。累積 -3.56 → **-5.92bp**。",
})
p["open_positions"] = [{"opened_report": "2026-09-23", "name": "破位空", "order": "sell_stop_close_confirm", "dir": "short",
                        "weight": 3, "fill_date": "2026-09-23", "fill_price": 30470.29, **ft,
                        "eval_on": "2026-09-24", "exit_rule": "次一交易日依浮動 T1／T2／停損判定；皆未觸及則收盤平倉。"}]
sm = p["summary"]
sm.update({"as_of": "2026-09-24", "days_evaluated": 19, "trades_total": 38, "signals_triggered": 20,
           "trades_filled": 18, "trades_not_triggered": 18, "filled_loss": 12,
           "fill_rate_pct": round(18 / 38 * 100, 1), "gap_invalidation_rate_pct": round(2 / 20 * 100, 1),
           "cumulative_weighted_bp": -5.92, "cumulative_if_intraday_checked": -8.21, "open_positions": 1,
           "honest_read": "累積 -3.56 → **-5.92bp**（30 分 K 揭露口徑 -8.21bp；prc-006 自 9/23 起兩口徑一致）。9/23 回踩多被利率衝擊掃掉 -2.36bp；破位空成交留倉。已結算成交 17 筆 5 勝 12 敗，另 1 筆留倉。"})
p["trades_pending"] = {
    "report_date": "2026-09-24", "basis_close": 30470.29,
    "eval_rule": "用 2026-09-24 美股 NDX OHLC 判定；適用 rule50（prc-004）與 rule51（prc-006，30 分 K 判序）。另判 open_positions 的 9/23 破位空。",
    "signal_atr14_pct": 1.284,
    "divergence_check": "【rule49】NDX 59 vs SPX 60 同側，且理由相同（利率衝擊、半導體轉弱）→ 同向，不減半。",
    "trades": [
        {"name": "反彈空（舊歷史高轉壓力）", "order": "limit_sell", "entry": 30661, "stop": 30790, "t1": 30360, "t2": 30196,
         "weight": 4, "dir": "short",
         "condition_note": "舊歷史收盤高 30,661 跌破後轉為壓力（9/23 11:00 後未再站回 30,533 之上）。停損置於 9/23 開盤高 30,706 與歷史盤中高 30,770 之上。RR 2.33／3.60。"},
        {"name": "回踩多（9/23 盤中雙底）", "order": "limit_buy", "entry": 30360, "stop": 30180, "t1": 30590, "t2": 30706,
         "weight": 3, "dir": "long",
         "condition_note": "錨定 9/23 盤中雙底 30,354.3（10:00）／30,355.0（13:00）。停損 8/17 高 30,196 之下。RR 1.28／1.92。逆利率衝擊接刀，倉位最小。"},
    ],
    "rejected_by_rule27": [
        {"name": "回踩多（8/17 高 30,196）", "entry": 30196, "dist_pct": -0.90, "threshold": 0.723, "reason": "超過門檻。"},
        {"name": "突破多（歷史高 30,771 之上）", "entry": 30775, "dist_pct": 1.0, "threshold": 0.723, "reason": "超過門檻，且利率環境不支持追高。"},
    ],
    "not_added": "不再加掛收盤確認空：9/23 破位空已留倉 3%，不疊加同型態部位。",
}
save("ndx_pnl_ledger.json", p)
open("ndx_update_0924.txt", "w", encoding="utf-8").write(f"OK mean={mean} n={len(inc)} ft={ft} atr={atr_pts}\n")
