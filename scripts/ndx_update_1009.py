import json

D = "../docs/"


def load(n):
    return json.load(open(D + n, encoding="utf-8"))


def save(n, o):
    json.dump(o, open(D + n, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


t = load("ndx_track_record.json")
e = t["entries"][-1]
assert e["report_date"] == "2026-10-08" and e["grade"] == "pending"
assert not any(x["report_date"] == "2026-10-09" for x in t["entries"])
e.update({
    "actual_date": "2026-10-08", "actual_pct": -1.39, "actual_dir": "down", "grade": "hit",
    "note": "10/8 開 30,985.23 → 高 31,125.13（10:00 棒）→ 午後急殺低 30,556.40（13:00 棒）→ 收 30,725.81（-1.39%）→ **down**。預測中性偏空 55% 遇 down → **hit**。Brier (0.55-1)² = 0.2025。\n\n"
            "【情景 C（35%）實現且超標】收盤 ≤ 31,035 成立，並跌破 30,904／30,798／30,746，收盤 30,725.81 < 30,737 → 第三類買點失效。\n\n"
            "【病因】FT 報導 OpenAI 營收不如預期 → AI 交易受挫，SOXX -3.35%；Brent +3.5% 至 103.7（伊朗戰事、荷莫茲油輪遇襲）。10Y 反落 5.231%，非利率驅動。",
})
t["entries"].append({"report_date": "2026-10-09", "basis_close": 30725.81, "basis_date": "2026-10-08",
                     "pullback_prob": 56, "bias": "中性偏空", "actual_date": None, "actual_pct": None,
                     "actual_dir": None, "grade": "pending"})
g = [x for x in t["entries"] if x.get("grade") in ("hit", "half", "miss")]
hits = sum(x["grade"] == "hit" for x in g); half = sum(x["grade"] == "half" for x in g); miss = sum(x["grade"] == "miss" for x in g)
score = round((hits + half * 0.5) / len(g) * 100, 1)
neu = [1.0 if x["actual_dir"] == "flat" else 0.5 for x in g]
neu_pct = round(sum(neu) / len(neu) * 100, 1)
s = t["summary"]
s.update({"as_of": "2026-10-09", "graded": len(g), "hits": hits, "half": half, "miss": miss,
          "rolling_direction_score_pct": score,
          "always_neutral_baseline_pct": neu_pct,
          "sample_caveat": f"n={len(g)}。{score}% ＝ ({hits} hit + {half} half×0.5 + {miss} miss) / {len(g)}。always-neutral 基準 {neu_pct}%（依 audit_20261002 須並列）。"})
b = s["brier"]
b["per_entry"].append({"report_date": "2026-10-08", "p": 0.55, "outcome": 1, "brier": 0.2025})
vals = [x["brier"] for x in b["per_entry"] if x["brier"] is not None]
b["included"] = len(vals)
b["excluded_flat"] = sum(1 for x in b["per_entry"] if x["brier"] is None)
b["mean_brier"] = round(sum(vals) / len(vals), 4)
b["as_of"] = "2026-10-09"
b["honest_read"] = f"mean brier 0.2444 → **{b['mean_brier']}**（n={b['included']}），略優於 0.25 基準。10/8 報 55 中性偏空遇 -1.39%，方向對但機率仍在窄帶。"
save("ndx_track_record.json", t)

p = load("ndx_pnl_ledger.json")
assert p["trades_pending"]["report_date"] == "2026-10-08"
assert not any(x["report_date"] == "2026-10-08" for x in p["entries"])
fill = 30725.81
atr_pts = round(fill * 1.199 / 100, 2)
ft = {"t1": round(fill - 0.8 * atr_pts, 2), "t2": round(fill - 1.6 * atr_pts, 2), "stop": round(fill + 0.8 * atr_pts, 2)}
p["entries"].append({
    "report_date": "2026-10-08", "basis_close": 31160.08, "eval_date": "2026-10-08",
    "eval_ohlc": {"open": 30985.23, "high": 31125.13, "low": 30556.4, "close": 30725.81},
    "rule50_check": "反彈空 limit_sell 開盤 30,985.23 < 停損 31,410 → 未跳空穿越；破位空為收盤確認單不適用。",
    "rule51_check": "無限價單成交，不需判序。",
    "trades": [
        {"name": "反彈空（缺口上緣／前收盤高 31,208–31,225）", "order": "limit_sell", "entry_signal": 31220, "dir": "short", "weight": 4,
         "signal_triggered": False, "filled": False, "status": "NOT_TRIGGERED — 全日高 31,125.13 未及 31,220",
         "pts": None, "ret_pct": None, "weighted_bp": 0.0},
        {"name": "破位空（收盤 < 31,035）", "order": "sell_stop_close_confirm", "entry_signal": 31035, "dir": "short", "weight": 5,
         "signal_triggered": True, "filled": True, "status": "FILLED → OPEN_POSITION（prc-001 留倉至次一交易日）",
         "fill_price": fill, "fill_note": "收盤 30,725.81 < 31,035，rule12 收盤確認成立；同時跌破 30,737 第三類買點失效位。", "slippage_pts": round(31035 - fill, 2),
         "floating_targets": {"atr_source": "訊號日 2026-10-07 的 ATR14 = 1.199%", "atr_pts": atr_pts, **ft,
                              "note": "T1 = 成交價 − 0.8 ATR、T2 = 成交價 − 1.6 ATR、停損 = 成交價 + 0.8 ATR。RR 恆為 1.00／2.00。"},
         "gap_check": "通過（浮動 T1 恆距成交價 0.8 ATR）。", "pts": None, "ret_pct": None, "weighted_bp": None},
    ],
    "day_weighted_bp": 0.0,
    "day_note": "反彈空未觸發、破位空成交留倉 → 當日 **0bp**（留倉待 10/9 判定）。累積維持 **-3.95bp**。",
})
p["open_positions"] = [{"opened_report": "2026-10-08", "name": "破位空", "order": "sell_stop_close_confirm", "dir": "short",
                        "weight": 5, "fill_date": "2026-10-08", "fill_price": fill, **ft,
                        "eval_on": "2026-10-09", "exit_rule": "次一交易日依浮動 T1／T2／停損判定；同日停損與目標皆觸及保守視為停損先到；皆未觸及則收盤平倉。"}]
sm = p["summary"]
sm.update({"as_of": "2026-10-09", "days_evaluated": sm["days_evaluated"] + 1,
           "trades_total": sm["trades_total"] + 2, "signals_triggered": sm["signals_triggered"] + 1,
           "trades_filled": sm["trades_filled"] + 1, "trades_not_triggered": sm["trades_not_triggered"] + 1,
           "open_positions": 1, "cumulative_weighted_bp": -3.95})
sm["fill_rate_pct"] = round(sm["trades_filled"] / sm["trades_total"] * 100, 1)
sm["gap_invalidation_rate_pct"] = round(sm["trades_gap_invalidated"] / sm["signals_triggered"] * 100, 1)
sm["honest_read"] = ("累積維持 **-3.95bp**（30 分 K 揭露口徑 -6.24bp）。rule52／53 生效後首張放行單：10/8 破位空收盤 30,725.81 成交留倉（滑價 309 點，浮動目標不受影響），"
                     "反彈空未觸發。已結算成交 21 筆 7 勝 14 敗，另 1 筆留倉。")
p["trades_pending"] = {
    "report_date": "2026-10-09", "basis_close": 30725.81,
    "eval_rule": "用 2026-10-09 美股 NDX OHLC 判定；limit_sell 開盤 ≥ 停損 → GAP_INVALIDATED（prc-004）；同日成交與觸價以 30 分 K 判序（rule51）。另判 open_positions 的 10/8 破位空（浮動 T1 %.2f／T2 %.2f／停損 %.2f）。" % (ft["t1"], ft["t2"], ft["stop"]),
    "signal_atr14_pct": 1.292,
    "divergence_check": "NDX 56 中性偏空 vs SPX 52 中性（rule62 全日不掛）→ 分歧，NDX 側倉位已減半。成因：VXN 21.98 中波動 vs VIX 15.41 低波動；AI／晶片衝擊集中在 NDX（SOXX -3.35%），SPX 等權撐住。",
    "trades": [
        {"name": "反彈空（10/7 低 30,904 轉壓力）", "order": "limit_sell", "entry": 30900, "dir": "short",
         "stop": 31135, "t1": 30560, "t2": 30365, "dist_pct": 0.57, "rr_t1": 1.45, "rr_t2": 2.28, "weight": 4,
         "note": "rule52：停損 max(0.5×ATR 199 點, 10/8 高 31,125 之上) → 31,135（235 點）。RR 1.45 → 倉位減半；與 SPX 分歧 → 已計入減半。"},
    ],
    "rejected_by_rule53": [
        {"name": "回踩多（10/8 低 30,556）", "order": "limit_buy", "entry": 30560, "dist_pct": -0.54, "reason": "逆 lean（bias 中性偏空）weight 0。"},
        {"name": "突破多（10/8 高 31,125 之上）", "order": "buy_stop", "entry": 31130, "dist_pct": 1.32, "reason": "逆 lean weight 0；且超 rule27 門檻 0.695%。"},
    ],
    "rejected_by_rule27": [
        {"name": "反彈空（MA5 30,999／10/8 開盤 30,985）", "order": "limit_sell", "entry": 30995, "dist_pct": 0.88, "reason": "距離 0.88% 超 rule27 門檻 0.695%。"},
    ],
    "not_added": "不再加掛收盤確認空：10/8 破位空已留倉 5%，不疊加同型態部位（比照 9/24 先例）。",
}
save("ndx_pnl_ledger.json", p)
open("ndx_update_1009.txt", "w", encoding="utf-8").write(f"OK graded={len(g)} score={score} neu={neu_pct} brier={b['mean_brier']} n={b['included']} days={sm['days_evaluated']} ft={ft} fill_rate={sm['fill_rate_pct']} gap={sm['gap_invalidation_rate_pct']}\n")
