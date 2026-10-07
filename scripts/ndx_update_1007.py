import json

D = "../docs/"


def load(n):
    return json.load(open(D + n, encoding="utf-8"))


def save(n, o):
    json.dump(o, open(D + n, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


t = load("ndx_track_record.json")
e = t["entries"][-1]
assert e["report_date"] == "2026-10-06" and e["grade"] == "pending"
assert not any(x["report_date"] == "2026-10-07" for x in t["entries"])
e.update({
    "actual_date": "2026-10-06", "actual_pct": 0.48, "actual_dir": "up", "grade": "half",
    "note": "10/6 開 31,255.40（跳空 +0.58%）→ 低 31,208.20（09:30 棒）→ 高 31,361.37（11:00 棒）→ 收 31,224.69（+0.48%）→ **up**。預測中性 53% 遇 up → **half**。Brier (0.53−0)² = 0.2809。\n\n"
            "【情景 A（28%）形式上實現】收盤 ≥ 31,201，收盤與盤中再創歷史新高；但跳空開高後走低，收在區間 10.8%、小黑 K，留下 31,117–31,208 跳空缺口。\n\n"
            "【當日】10Y 回落至約 5.27%（-4bps）、VXN 21.7 → 21.15；NVDA、AMD 創高，S&P 500 首度收在 7,800 之上。SOXX -0.01% 連兩日未跟、QQQ 量 78.9%。",
})
t["entries"].append({"report_date": "2026-10-07", "basis_close": 31224.69, "basis_date": "2026-10-06",
                     "pullback_prob": 54, "bias": "中性", "actual_date": None, "actual_pct": None,
                     "actual_dir": None, "grade": "pending"})
g = [x for x in t["entries"] if x.get("grade") in ("hit", "half", "miss")]
hits = sum(x["grade"] == "hit" for x in g); half = sum(x["grade"] == "half" for x in g); miss = sum(x["grade"] == "miss" for x in g)
score = round((hits + half * 0.5) / len(g) * 100, 1)
neu = [1.0 if x["actual_dir"] == "flat" else 0.5 for x in g]
neu_pct = round(sum(neu) / len(neu) * 100, 1)
s = t["summary"]
s.update({"as_of": "2026-10-07", "graded": len(g), "hits": hits, "half": half, "miss": miss,
          "rolling_direction_score_pct": score,
          "always_neutral_baseline_pct": neu_pct,
          "sample_caveat": f"n={len(g)}。{score}% ＝ ({hits} hit + {half} half×0.5 + {miss} miss) / {len(g)}。always-neutral 基準 {neu_pct}%（依 audit_20261002 須並列）。"})
b = s["brier"]
b["per_entry"].append({"report_date": "2026-10-06", "p": 0.53, "outcome": 0, "brier": 0.2809})
vals = [x["brier"] for x in b["per_entry"] if x["brier"] is not None]
b["included"] = len(vals)
b["mean_brier"] = round(sum(vals) / len(vals), 4)
b["as_of"] = "2026-10-07"
b["honest_read"] = f"mean brier **{b['mean_brier']}**（n={b['included']}），與 0.25 基準相當。10/6 報 53 遇漲 +0.48%，Brier 0.2809——連三日中性偏空側遇創高。"
save("ndx_track_record.json", t)

p = load("ndx_pnl_ledger.json")
assert p["trades_pending"]["report_date"] == "2026-10-06"
assert not any(x["report_date"] == "2026-10-06" for x in p["entries"])
p["entries"].append({
    "report_date": "2026-10-06", "basis_close": 31076.44, "eval_date": "2026-10-06",
    "eval_ohlc": {"open": 31255.4, "high": 31361.37, "low": 31208.2, "close": 31224.69},
    "rule50_check": "rule53 全日不掛，無單可判。",
    "rule51_check": "無成交單，不需判序。",
    "trades": [],
    "day_weighted_bp": 0.0,
    "shadow_rejected": "【僅揭露、不計帳】被 rule53 擋下的單：突破多 buy_stop 31,120 跳空開在 31,255 成交（滑價 135 點），10:30 棒高 31,333.7 觸 T1 31,330 → 約 +0.24%；反彈空 limit_sell 31,250 開盤即成交，停損 31,460 與 T1 31,000 皆未觸，收 31,224.69 → 約 +0.08%；回踩多 30,960 與破位空未觸發。兩張皆小賺，rule53 本日少賺約 +0.3%（未乘權重）。",
    "day_note": "rule53 全日不掛 → 當日 **0bp**。累積維持 **-3.95bp**。",
})
sm = p["summary"]
sm.update({"as_of": "2026-10-07", "days_evaluated": sm["days_evaluated"] + 1,
           "cumulative_weighted_bp": -3.95,
           "honest_read": "累積維持 **-3.95bp**（30 分 K 揭露口徑 -6.24bp）。rule52／53 生效後連三日（10/5–10/7 報告）中性全日不掛；影子帳 10/5 擋下約 -0.74bp、10/6 擋下兩張小賺單（約 +0.24%／+0.08%）→ 新制目前影子淨效果接近 0。成交 21 筆 7 勝 14 敗。"})
p["trades_pending"] = {
    "report_date": "2026-10-07", "basis_close": 31224.69,
    "eval_rule": "用 2026-10-07 美股 NDX OHLC 判定。**本日 rule53 全日不掛**（bias 中性、headline 54 落在 46–54），無單可評估；明日記 0bp 並更新 days_evaluated。",
    "signal_atr14_pct": 1.249,
    "divergence_check": "NDX 54 vs SPX 47 同為中性、同為全日不掛。regime：VXN 中波動 +1.5pp vs SPX VIX<16 -6.2pp → 波動檔分歧持續（連三日）。",
    "trades": [],
    "rejected_by_rule53": [
        {"name": "回踩多（缺口下緣 31,120）", "order": "limit_buy", "entry": 31120, "stop": 30920, "t1": 31361, "dist_pct": -0.33, "rr_t1": 1.21,
         "reason": "rule53 中性全日不掛；即使可掛，RR 1.21 依 rule52 倉位減半。"},
        {"name": "反彈空（31,400）", "order": "limit_sell", "entry": 31400, "stop": 31600, "t1": 31120, "dist_pct": 0.56, "rr_t1": 1.40,
         "reason": "rule53 中性全日不掛。"},
        {"name": "破位空（收盤 < 31,100）", "order": "sell_stop_close_confirm", "entry": 31100, "dist_pct": -0.40,
         "reason": "rule53 中性全日不掛。"},
        {"name": "突破多（31,370 歷史高之上）", "order": "buy_stop", "entry": 31370, "stop": 31170, "t1": 31549, "dist_pct": 0.46, "rr_t1": 0.90,
         "reason": "rule53 中性全日不掛；rule52 RR 0.90 <1.0；QQQ 量 78.9% 未達 rule43 帶量。"},
    ],
    "rejected_by_rule27": [],
}
save("ndx_pnl_ledger.json", p)
open("ndx_update_1007.txt", "w", encoding="utf-8").write(f"OK graded={len(g)} score={score} neu={neu_pct} brier={b['mean_brier']} n={b['included']} days={sm['days_evaluated']}\n")
