import json

D = "../docs/"


def load(n):
    return json.load(open(D + n, encoding="utf-8"))


def save(n, o):
    json.dump(o, open(D + n, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


O, H, L, C = 30796.04, 30813.96, 30618.64, 30664.70

t = load("ndx_track_record.json")
e = t["entries"][-1]
assert e["report_date"] == "2026-10-12" and e["grade"] == "pending"
assert not any(x["report_date"] == "2026-10-13" for x in t["entries"])
e.update({
    "actual_date": "2026-10-12", "actual_pct": -0.71, "actual_dir": "down", "grade": "half",
    "note": "10/12 開 30,796.04（跳空 -0.28%）→ 高 30,813.96（09:30 棒）→ 低 30,618.64（14:30 棒）→ 收 30,664.70（-0.71%）→ **down**。預測中性 53% 遇 down → **half**。Brier (0.53-1)² = 0.2209。\n\n"
            "【情景 C（32%）實現】收盤 ≤ 30,760 成立：跌破 10/9 inside day 下緣 30,770 與 0.236 回撤 30,746，但低點 30,619 守在 10/8 低 30,556 之上。\n\n"
            "【病因】記憶體領跌晶片（報導：長鑫存儲技術進展 → Micron -3.9%；SOXX -2.60%、5 日 -7.58%），加上沙烏地遭襲、Brent 升至兩週高。SPX 僅 -0.06%，跌勢集中在科技側。\n\n"
            "【偏差】偏空理由（rule15 連兩日、量縮反彈、反彈未及 MA5）事前都列了，但只給到 53；方向對、幅度不敢報。依 rule53 未掛單，無損益。",
})
t["entries"].append({"report_date": "2026-10-13", "basis_close": C, "basis_date": "2026-10-12",
                     "pullback_prob": 52, "bias": "中性", "actual_date": None, "actual_pct": None,
                     "actual_dir": None, "grade": "pending"})
g = [x for x in t["entries"] if x.get("grade") in ("hit", "half", "miss")]
hits = sum(x["grade"] == "hit" for x in g); half = sum(x["grade"] == "half" for x in g); miss = sum(x["grade"] == "miss" for x in g)
score = round((hits + half * 0.5) / len(g) * 100, 1)
neu = [1.0 if x["actual_dir"] == "flat" else 0.5 for x in g]
neu_pct = round(sum(neu) / len(neu) * 100, 1)
s = t["summary"]
s.update({"as_of": "2026-10-13", "graded": len(g), "hits": hits, "half": half, "miss": miss,
          "rolling_direction_score_pct": score,
          "always_neutral_baseline_pct": neu_pct,
          "sample_caveat": f"n={len(g)}。{score}% ＝ ({hits} hit + {half} half×0.5 + {miss} miss) / {len(g)}。always-neutral 基準 {neu_pct}%（依 audit_20261002 須並列）。"})
b = s["brier"]
prev_mean = b["mean_brier"]
assert not any(x["report_date"] == "2026-10-12" for x in b["per_entry"])
b["per_entry"].append({"report_date": "2026-10-12", "p": 0.53, "outcome": 1, "brier": 0.2209})
vals = [x["brier"] for x in b["per_entry"] if x["brier"] is not None]
b["included"] = len(vals)
b["excluded_flat"] = sum(1 for x in b["per_entry"] if x["brier"] is None)
b["mean_brier"] = round(sum(vals) / len(vals), 4)
b["as_of"] = "2026-10-13"
b["honest_read"] = f"mean brier {prev_mean} → **{b['mean_brier']}**（n={b['included']}），貼近 0.25 基準、幾乎沒有資訊量。10/12 報 53 中性遇 -0.71% → half。"
save("ndx_track_record.json", t)

p = load("ndx_pnl_ledger.json")
assert p["trades_pending"]["report_date"] == "2026-10-12" and p["trades_pending"]["trades"] == []
assert not any(x["report_date"] == "2026-10-12" for x in p["entries"])
assert p["open_positions"] == []
sm = p["summary"]
cum = sm["cumulative_weighted_bp"]
p["entries"].append({
    "report_date": "2026-10-12", "basis_close": 30883.15, "eval_date": "2026-10-12",
    "eval_ohlc": {"open": O, "high": H, "low": L, "close": C},
    "rule50_check": "rule53 全日不掛，無單可判。",
    "rule51_check": "無成交單，不需判序。",
    "trades": [],
    "day_weighted_bp": 0.0,
    "shadow_rejected": "【僅揭露、不計帳】被 rule53 擋下的單：回踩多 limit_buy 30,770 於 09:30 棒成交（開 30,792、低 30,719），停損 30,546 未觸（全日低 30,619）、T1 30,947 未觸 → 收盤 30,664.70 約 -0.34%；反彈空 30,945 未觸發（高 30,814）；破位空收盤 30,665 > 30,556 未觸發；突破多 31,130 未觸發。",
    "day_note": f"rule53 全日不掛 → 當日 **0bp**。累積維持 **{cum}bp**。",
})
sm.update({"as_of": "2026-10-13", "days_evaluated": sm["days_evaluated"] + 1})
sm["honest_read"] = (f"累積維持 **{cum}bp**（30 分 K 揭露口徑 {sm['cumulative_if_intraday_checked']}bp）。10/12 rule53 全日不掛，記 0bp；"
                     f"被擋下的回踩多若掛出會以約 -0.34% 收盤（僅揭露）。已結算成交 {sm['filled_win'] + sm['filled_loss']} 筆 {sm['filled_win']} 勝 {sm['filled_loss']} 敗，無留倉。")
p["trades_pending"] = {
    "report_date": "2026-10-13", "basis_close": C,
    "eval_rule": "用 2026-10-13 美股 NDX OHLC 判定。**本日 rule53 全日不掛**（bias 中性、headline 52 落在 46–54），無單可評估、無留倉；明日記 0bp 並更新 days_evaluated。",
    "signal_atr14_pct": 1.128,
    "divergence_check": "NDX 52 vs SPX 53 同為中性、同為全日不掛。數字接近但成因不同：SPX 10/12 只跌 0.06%、振幅 0.32% 貼著高點壓縮；NDX 跌 0.71%、跌破 10/9 inside day 下緣與 0.236 回撤，SOXX 連三日落後。VXN 20.84 中波動 vs VIX 15.21 低波動。",
    "trades": [],
    "rejected_by_rule53": [
        {"name": "反彈空（10/9 低 30,770 轉壓力）", "order": "limit_sell", "entry": 30770, "stop": 30957, "t1": 30619, "dist_pct": 0.34, "rr_t1": 0.81,
         "reason": "rule53 中性全日不掛；rule52 停損須在 MA5 30,932／10/9 高 30,947 之外（187 點）→ RR 0.81 <1.0。"},
        {"name": "回踩多（10/8 低 30,556）", "order": "limit_buy", "entry": 30560, "stop": 30380, "t1": 30770, "dist_pct": -0.34, "rr_t1": 1.17,
         "reason": "rule53 中性全日不掛；rule8 不掛限價單在支撐等接。rule52 停損 30,380（MA20 之外，180 點）下 RR 1.17，即使可掛亦須減半。"},
        {"name": "破位空（收盤 < 30,556）", "order": "sell_stop_close_confirm", "entry": 30556, "dist_pct": -0.35,
         "reason": "rule53 中性全日不掛（距離 0.35% 在 rule27 門檻內，純因中性被擋）。"},
    ],
    "rejected_by_rule27": [
        {"name": "突破多（10/9 高 30,947 之上）", "order": "buy_stop", "entry": 30950, "dist_pct": 0.93, "reason": "rule53 中性全日不掛；距離 0.93% 亦超 rule27 門檻 0.603%。"},
    ],
}
save("ndx_pnl_ledger.json", p)
open("ndx_update_1013.txt", "w", encoding="utf-8").write(
    f"OK graded={len(g)} h={hits} half={half} m={miss} score={score} neu={neu_pct} brier={prev_mean}->{b['mean_brier']} n={b['included']} flat={b['excluded_flat']} "
    f"days={sm['days_evaluated']} cum={cum} intraday={sm['cumulative_if_intraday_checked']} total={sm['trades_total']} filled={sm['trades_filled']}\n")
