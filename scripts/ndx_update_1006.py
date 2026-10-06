import json

D = "../docs/"


def load(n):
    return json.load(open(D + n, encoding="utf-8"))


def save(n, o):
    json.dump(o, open(D + n, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


t = load("ndx_track_record.json")
e = t["entries"][-1]
assert e["report_date"] == "2026-10-05" and e["grade"] == "pending"
assert not any(x["report_date"] == "2026-10-06" for x in t["entries"])
e.update({
    "actual_date": "2026-10-05", "actual_pct": 0.87, "actual_dir": "up", "grade": "half",
    "note": "10/5 開 30,812.76（≈平）→ 低 30,798.42（09:30 棒）→ 高 31,117.36（15:00 棒）→ 收 31,076.44（+0.87%）→ **up**。預測中性 52% 遇 up → **half**。Brier (0.52−0)² = 0.2704。\n\n"
            "【情景 A（29%）實現】收盤 ≥ 30,931，收盤與盤中再創歷史新高；回踩低 30,798 守住缺口上緣 30,737 → 第三類買點成立。\n\n"
            "【當日】10Y 收約 5.31%（2002 年以來最高收盤）、ISM 服務業物價分項 74.0；NVDA +2.1% 創高、油價回落。QQQE +0.74% 落後 QQQ +0.88%、SOXX 僅 +0.10%。",
})
t["entries"].append({"report_date": "2026-10-06", "basis_close": 31076.44, "basis_date": "2026-10-05",
                     "pullback_prob": 53, "bias": "中性", "actual_date": None, "actual_pct": None,
                     "actual_dir": None, "grade": "pending"})
g = [x for x in t["entries"] if x.get("grade") in ("hit", "half", "miss")]
hits = sum(x["grade"] == "hit" for x in g); half = sum(x["grade"] == "half" for x in g); miss = sum(x["grade"] == "miss" for x in g)
score = round((hits + half * 0.5) / len(g) * 100, 1)
neu = [1.0 if x["actual_dir"] == "flat" else 0.5 for x in g]
neu_pct = round(sum(neu) / len(neu) * 100, 1)
s = t["summary"]
s.update({"as_of": "2026-10-06", "graded": len(g), "hits": hits, "half": half, "miss": miss,
          "rolling_direction_score_pct": score,
          "always_neutral_baseline_pct": neu_pct,
          "sample_caveat": f"n={len(g)}。{score}% ＝ ({hits} hit + {half} half×0.5 + {miss} miss) / {len(g)}。always-neutral 基準 {neu_pct}%（依 audit_20261002 須並列）。"})
b = s["brier"]
b["per_entry"].append({"report_date": "2026-10-05", "p": 0.52, "outcome": 0, "brier": 0.2704})
vals = [x["brier"] for x in b["per_entry"] if x["brier"] is not None]
b["included"] = len(vals)
b["mean_brier"] = round(sum(vals) / len(vals), 4)
b["as_of"] = "2026-10-06"
b["honest_read"] = f"mean brier **{b['mean_brier']}**（n={b['included']}），仍僅略優於 0.25 基準。10/5 報 52 遇漲 +0.87%，Brier 0.2704——連兩日中性偏空側遇創高。"
save("ndx_track_record.json", t)

p = load("ndx_pnl_ledger.json")
assert p["trades_pending"]["report_date"] == "2026-10-05"
assert not any(x["report_date"] == "2026-10-05" for x in p["entries"])
p["entries"].append({
    "report_date": "2026-10-05", "basis_close": 30807.93, "eval_date": "2026-10-05",
    "eval_ohlc": {"open": 30812.76, "high": 31117.36, "low": 30798.42, "close": 31076.44},
    "rule50_check": "rule53 全日不掛，無單可判。",
    "rule51_check": "無成交單，不需判序。",
    "trades": [],
    "day_weighted_bp": 0.0,
    "shadow_rejected": "【僅揭露、不計帳】被 rule53 擋下的三張：回踩多 30,740 未觸發（低 30,798）；反彈空 31,000 會在 11:00 棒成交（高 31,005.6）、未觸停損 31,200、收盤 31,076 → 約 -0.25%×3 ≈ -0.74bp；破位空未觸發。rule53 讓帳本避開約 -0.74bp。",
    "day_note": "rule53 全日不掛 → 當日 **0bp**。累積維持 **-3.95bp**。",
})
sm = p["summary"]
sm.update({"as_of": "2026-10-06", "days_evaluated": sm["days_evaluated"] + 1,
           "cumulative_weighted_bp": -3.95,
           "honest_read": "累積維持 **-3.95bp**（30 分 K 揭露口徑 -6.24bp）。rule52／53 生效後連兩日（10/5、10/6 報告）中性全日不掛；10/5 影子帳顯示 rule53 擋下一筆約 -0.74bp 的反彈空。成交 21 筆 7 勝 14 敗。"})
p["trades_pending"] = {
    "report_date": "2026-10-06", "basis_close": 31076.44,
    "eval_rule": "用 2026-10-06 美股 NDX OHLC 判定。**本日 rule53 全日不掛**（bias 中性、headline 53 落在 46–54），無單可評估；明日記 0bp 並更新 days_evaluated。",
    "signal_atr14_pct": 1.3,
    "divergence_check": "NDX 53 vs SPX 48 同為中性、同為全日不掛。regime：VXN 中波動 +1.5pp vs SPX VIX<16 -6.2pp → 波動檔分歧持續。",
    "trades": [],
    "rejected_by_rule53": [
        {"name": "回踩多（10/5 午盤平台 30,960）", "order": "limit_buy", "entry": 30960, "stop": 30750, "t1": 31117, "dist_pct": -0.37, "rr_t1": 0.75,
         "reason": "rule53 中性全日不掛；且依 rule52 停損放寬到 0.5 ATR 外後 T1 RR 0.75 <1.0，本來就不掛。"},
        {"name": "反彈空（31,250）", "order": "limit_sell", "entry": 31250, "stop": 31460, "t1": 31000, "dist_pct": 0.56, "rr_t1": 1.19,
         "reason": "rule53 中性全日不掛。"},
        {"name": "破位空（收盤 < 30,873）", "order": "sell_stop_close_confirm", "entry": 30873, "dist_pct": -0.65,
         "reason": "rule53 中性全日不掛。"},
        {"name": "突破多（31,120 歷史高之上）", "order": "buy_stop", "entry": 31120, "stop": 30915, "t1": 31330, "dist_pct": 0.14, "rr_t1": 1.02,
         "reason": "rule53 中性全日不掛；QQQ 量 75.4% 未達 rule43 帶量。"},
    ],
    "rejected_by_rule27": [],
}
save("ndx_pnl_ledger.json", p)
open("ndx_update_1006.txt", "w", encoding="utf-8").write(f"OK graded={len(g)} score={score} neu={neu_pct} brier={b['mean_brier']} n={b['included']} days={sm['days_evaluated']}\n")
