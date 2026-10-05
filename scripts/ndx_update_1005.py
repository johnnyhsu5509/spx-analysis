import json

D = "../docs/"


def load(n):
    return json.load(open(D + n, encoding="utf-8"))


def save(n, o):
    json.dump(o, open(D + n, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


t = load("ndx_track_record.json")
e = t["entries"][-1]
assert e["report_date"] == "2026-10-02" and e["grade"] == "pending"
assert not any(x["report_date"] == "2026-10-05" for x in t["entries"])
e.update({
    "actual_date": "2026-10-02", "actual_pct": 1.0, "actual_dir": "up", "grade": "half",
    "note": "10/2 開 30,869.14（跳空 +1.21%）→ 高 31,017.53（10:00 棒）→ 低 30,737.07（11:00 棒）→ 收 30,807.93（+1.00%）→ **up**。預測中性 49% 遇 up → **half**。Brier (0.49−0)² = 0.2401。\n\n"
            "【情景 A（31%）實現】收盤 > 30,624，向上離開七日中樞，收盤與盤中皆創歷史新高。\n\n"
            "【當日】非農 +2.9 萬（預期約 8 萬）、失業率 4.2%，升息預期退燒；10Y 先跌到約 5.17% 後反轉收約 5.28%。SOXX +2.18%、NVDA 新高。但開高走低收黑 K，收在區間 25%，等權 QQQE +0.61% 落後 QQQ +1.02%。",
})
t["entries"].append({"report_date": "2026-10-05", "basis_close": 30807.93, "basis_date": "2026-10-02",
                     "pullback_prob": 52, "bias": "中性", "actual_date": None, "actual_pct": None,
                     "actual_dir": None, "grade": "pending"})
s = t["summary"]
s.update({"as_of": "2026-10-05", "graded": 23, "hits": 10, "half": 10, "miss": 3,
          "rolling_direction_score_pct": 65.2,
          "sample_caveat": "n=23。65.2% ＝ (10 hit + 10 half×0.5 + 3 miss) / 23 = 15/23。"})
b = s["brier"]
b["per_entry"].append({"report_date": "2026-10-02", "p": 0.49, "outcome": 0, "brier": 0.2401})
vals = [x["brier"] for x in b["per_entry"] if x["brier"] is not None]
b["included"] = len(vals)
b["mean_brier"] = round(sum(vals) / len(vals), 4)
b["as_of"] = "2026-10-05"
b["honest_read"] = f"mean brier **{b['mean_brier']}**（n={b['included']}），仍僅略優於 0.25 基準。10/2 報 49 遇漲 +1.0%，Brier 0.2401——中性報價的代價就是接近基準。"
save("ndx_track_record.json", t)

p = load("ndx_pnl_ledger.json")
assert p["trades_pending"]["report_date"] == "2026-10-02"
assert not any(x["report_date"] == "2026-10-02" for x in p["entries"])
p["entries"].append({
    "report_date": "2026-10-02", "basis_close": 30501.56, "eval_date": "2026-10-02",
    "eval_ohlc": {"open": 30869.14, "high": 31017.53, "low": 30737.07, "close": 30807.93},
    "rule50_check": "反彈空掛 30,615、停損 30,815：開盤 30,869.14 ≥ 停損 → **GAP_INVALIDATED（prc-004）**。回踩多 30,300：全日低 30,737.07 未觸及。",
    "rule51_check": "無成交單，不需判序。",
    "trades": [
        {"name": "反彈空（雙頂 30,616／30,630）", "order": "limit_sell", "entry_signal": 30615, "dir": "short", "weight": 3,
         "signal_triggered": True, "filled": False,
         "status": "GAP_INVALIDATED — 開盤 30,869.14 已高於停損 30,815（prc-004）",
         "fill_price": None, "exit_price": None, "exit_reason": None, "pts": None, "ret_pct": None, "weighted_bp": 0.0,
         "note": "非農跳空直接穿越停損。若無 prc-004 照實成交，以停損計約 -0.65%×3 ≈ -1.96bp；規則讓帳本避開了一筆實務上不會進場的單。"},
        {"name": "回踩多（10/1 低）", "order": "limit_buy", "entry_signal": 30300, "dir": "long", "weight": 3,
         "signal_triggered": False, "filled": False, "status": "NOT_TRIGGERED — 低 30,737.07 遠高於 30,300",
         "pts": None, "ret_pct": None, "weighted_bp": 0.0},
    ],
    "day_weighted_bp": 0.0,
    "day_note": "反彈空 GAP_INVALIDATED、回踩多未觸發 → 當日 **0bp**。累積維持 **-3.95bp**。",
})
sm = p["summary"]
sm.update({"as_of": "2026-10-05", "days_evaluated": 23, "trades_total": 46, "signals_triggered": 24,
           "trades_filled": 21, "trades_gap_invalidated": 3, "trades_not_triggered": 22,
           "fill_rate_pct": round(21 / 46 * 100, 1), "gap_invalidation_rate_pct": round(3 / 24 * 100, 1),
           "cumulative_weighted_bp": -3.95,
           "honest_read": "累積維持 **-3.95bp**（30 分 K 揭露口徑 -6.24bp）。10/2 非農跳空讓反彈空依 prc-004 失效、回踩多未觸發。成交 21 筆 7 勝 14 敗。10/5 起 rule52／53 生效，首日即因中性全日不掛。"})
p["trades_pending"] = {
    "report_date": "2026-10-05", "basis_close": 30807.93,
    "eval_rule": "用 2026-10-05 美股 NDX OHLC 判定。**本日 rule53 全日不掛**（bias 中性、headline 52 落在 46–54），無單可評估；明日只需記 0bp 並更新 days_evaluated。",
    "signal_atr14_pct": 1.294,
    "divergence_check": "NDX 52 vs SPX 49 同為中性、同為全日不掛。regime：VXN 中波動 +1.5pp vs SPX VIX<16 -6.2pp → 波動檔分歧，風險集中在科技側。",
    "trades": [],
    "rejected_by_rule53": [
        {"name": "回踩多（缺口上緣 30,737）", "order": "limit_buy", "entry": 30740, "stop": 30540, "t1": 31000, "dist_pct": -0.22, "rr_t1": 1.3,
         "reason": "rule53 中性全日不掛；即使可掛，RR 1.3 依 rule52 亦須減半。"},
        {"name": "反彈空（31,000 前高）", "order": "limit_sell", "entry": 31000, "stop": 31200, "t1": 30740, "dist_pct": 0.62, "rr_t1": 1.3,
         "reason": "rule53 中性全日不掛。"},
        {"name": "破位空（收盤 < 30,616 回補缺口）", "order": "sell_stop_close_confirm", "entry": 30615, "dist_pct": -0.63,
         "reason": "rule53 中性全日不掛。"},
    ],
    "rejected_by_rule27": [
        {"name": "突破多（31,018 歷史高之上）", "entry": 31020, "dist_pct": 0.69, "threshold": 0.671, "reason": "超過門檻；且 QQQ 量 102.5% 未達 rule43 帶量。"},
    ],
}
save("ndx_pnl_ledger.json", p)
open("ndx_update_1005.txt", "w", encoding="utf-8").write("OK\n")
