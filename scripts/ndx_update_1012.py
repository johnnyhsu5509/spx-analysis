import json

D = "../docs/"


def load(n):
    return json.load(open(D + n, encoding="utf-8"))


def save(n, o):
    json.dump(o, open(D + n, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


t = load("ndx_track_record.json")
e = t["entries"][-1]
assert e["report_date"] == "2026-10-09" and e["grade"] == "pending"
assert not any(x["report_date"] == "2026-10-12" for x in t["entries"])
e.update({
    "actual_date": "2026-10-09", "actual_pct": 0.51, "actual_dir": "up", "grade": "miss",
    "note": "10/9 開 30,900.06（跳空 +0.57%）→ 高 30,946.74（09:30 棒）→ 低 30,770.05（10:00 棒）→ 收 30,883.15（+0.51%）→ **up**。預測中性偏空 56% 遇 up → **miss**。Brier (0.56-0)² = 0.3136。\n\n"
            "【情景 A（26%）實現】收盤 ≥ 30,849 成立，但高點 30,947 止於 30,904 壓力上方 43 點、未及 MA5；全日為 10/8 區間內的 inside day，振幅僅 0.57%。\n\n"
            "【病因】沒有新利多：10/8 AI 殺盤後的技術反彈＋油價、殖利率停止上衝。QQQ 量僅 20 日均 61.6%，SOXX -0.69% 續跌。\n\n"
            "【偏差】10/8 帶量長黑後隔日直接報偏空，低估了趨勢日後的均值回歸；56 與 50 只差 6pp 卻掛了空單，方向判斷的資訊量不足以支撐倉位。",
})
t["entries"].append({"report_date": "2026-10-12", "basis_close": 30883.15, "basis_date": "2026-10-09",
                     "pullback_prob": 53, "bias": "中性", "actual_date": None, "actual_pct": None,
                     "actual_dir": None, "grade": "pending"})
g = [x for x in t["entries"] if x.get("grade") in ("hit", "half", "miss")]
hits = sum(x["grade"] == "hit" for x in g); half = sum(x["grade"] == "half" for x in g); miss = sum(x["grade"] == "miss" for x in g)
score = round((hits + half * 0.5) / len(g) * 100, 1)
neu = [1.0 if x["actual_dir"] == "flat" else 0.5 for x in g]
neu_pct = round(sum(neu) / len(neu) * 100, 1)
s = t["summary"]
s.update({"as_of": "2026-10-12", "graded": len(g), "hits": hits, "half": half, "miss": miss,
          "rolling_direction_score_pct": score,
          "always_neutral_baseline_pct": neu_pct,
          "sample_caveat": f"n={len(g)}。{score}% ＝ ({hits} hit + {half} half×0.5 + {miss} miss) / {len(g)}。always-neutral 基準 {neu_pct}%（依 audit_20261002 須並列）。"})
b = s["brier"]
prev_mean = b["mean_brier"]
b["per_entry"].append({"report_date": "2026-10-09", "p": 0.56, "outcome": 0, "brier": 0.3136})
vals = [x["brier"] for x in b["per_entry"] if x["brier"] is not None]
b["included"] = len(vals)
b["excluded_flat"] = sum(1 for x in b["per_entry"] if x["brier"] is None)
b["mean_brier"] = round(sum(vals) / len(vals), 4)
b["as_of"] = "2026-10-12"
b["honest_read"] = f"mean brier {prev_mean} → **{b['mean_brier']}**（n={b['included']}），貼近 0.25 基準、幾乎沒有資訊量。10/9 報 56 中性偏空遇 +0.51% → miss。"
save("ndx_track_record.json", t)

p = load("ndx_pnl_ledger.json")
assert p["trades_pending"]["report_date"] == "2026-10-09"
assert not any(x["report_date"] == "2026-10-09" for x in p["entries"])
op = p["open_positions"][0]
assert op["fill_price"] == 30725.81 and op["eval_on"] == "2026-10-09"
O, H, L, C = 30900.06, 30946.74, 30770.05, 30883.15
assert H < op["stop"] and L > op["t1"]
op_pts = round(op["fill_price"] - C, 2)
op_ret = round(op_pts / op["fill_price"] * 100, 4)
op_bp = round(op_ret * op["weight"], 2)
entry, stop, t1, w = 30900, 31135, 30560, 4
assert O < stop and H >= entry and H < stop and L > t1
rs_pts = round(entry - C, 2)
rs_ret = round(rs_pts / entry * 100, 4)
rs_bp = round(rs_ret * w, 2)
day = round(op_bp + rs_bp, 2)
sm = p["summary"]
cum0 = sm["cumulative_weighted_bp"]
cum = round(cum0 + day, 2)
p["entries"].append({
    "report_date": "2026-10-09", "basis_close": 30725.81, "eval_date": "2026-10-09",
    "eval_ohlc": {"open": O, "high": H, "low": L, "close": C},
    "rule50_check": "反彈空 limit_sell 開盤 30,900.06 < 停損 31,135 → 未跳空穿越（prc-004），正常成交。",
    "rule51_check": "反彈空於 09:30 首棒成交（開盤 30,900.06 已在掛單價 30,900 之上，30 分 K 高 30,945.8）；成交後全日高 30,946.74 未及停損 31,135、低 30,770.05 未及 T1 30,560 → 收盤平倉。",
    "closed_positions": [
        {"name": "破位空（10/8 成交）", "order": "sell_stop_close_confirm", "dir": "short", "weight": op["weight"],
         "fill_price": op["fill_price"], "t1": op["t1"], "t2": op["t2"], "stop": op["stop"],
         "exit_price": C, "exit_reason": "收盤平倉（高 30,946.74 距浮動停損 31,020.53 尚有 73.79 點；低 30,770.05 未及浮動 T1 30,431.09）",
         "pts": op_pts, "ret_pct": op_ret, "weighted_bp": op_bp},
    ],
    "trades": [
        {"name": "反彈空（10/7 低 30,904 轉壓力）", "order": "limit_sell", "entry_signal": entry, "dir": "short", "weight": w,
         "signal_triggered": True, "filled": True, "status": "FILLED → 收盤平倉",
         "fill_price": entry, "exit_price": C, "exit_reason": "收盤平倉（T1 30,560、停損 31,135 皆未觸及）",
         "pts": rs_pts, "ret_pct": rs_ret, "weighted_bp": rs_bp,
         "fill_note": "開盤 30,900.06 略高於掛單價，帳本依慣例以掛單價 30,900 計（差 0.06 點）。"},
    ],
    "day_weighted_bp": day,
    "day_note": f"留倉破位空收盤平倉 {op_bp}bp、反彈空收盤平倉 +{rs_bp}bp → 當日 **{day}bp**。累積 {cum0} → **{cum}bp**。",
})
p["open_positions"] = []
sm.update({"as_of": "2026-10-12", "days_evaluated": sm["days_evaluated"] + 1,
           "trades_total": sm["trades_total"] + 1, "signals_triggered": sm["signals_triggered"] + 1,
           "trades_filled": sm["trades_filled"] + 1,
           "filled_win": sm["filled_win"] + 1, "filled_loss": sm["filled_loss"] + 1,
           "open_positions": 0, "cumulative_weighted_bp": cum,
           "cumulative_if_intraday_checked": round(sm["cumulative_if_intraday_checked"] + day, 2)})
sm["fill_rate_pct"] = round(sm["trades_filled"] / sm["trades_total"] * 100, 1)
sm["gap_invalidation_rate_pct"] = round(sm["trades_gap_invalidated"] / sm["signals_triggered"] * 100, 1)
sm["honest_read"] = (f"累積 {cum0} → **{cum}bp**（30 分 K 揭露口徑 {sm['cumulative_if_intraday_checked']}bp）。rule53 首次放行的兩張空單結算：10/8 破位空（收盤成交、滑價 309 點）隔日反彈收盤平倉 {op_bp}bp；"
                     f"10/9 反彈空開盤成交、收盤平倉 +{rs_bp}bp。已結算成交 {sm['filled_win'] + sm['filled_loss']} 筆 {sm['filled_win']} 勝 {sm['filled_loss']} 敗，無留倉。")
p["trades_pending"] = {
    "report_date": "2026-10-12", "basis_close": C,
    "eval_rule": "用 2026-10-12 美股 NDX OHLC 判定。**本日 rule53 全日不掛**（bias 中性、headline 53 落在 46–54），無單可評估、無留倉；明日記 0bp 並更新 days_evaluated。",
    "signal_atr14_pct": 1.125,
    "divergence_check": "NDX 53 vs SPX 47 同為中性、同為全日不掛，但偏向相反（NDX 略偏空、SPX 略偏多）。成因：SPX 已站回 10/7 高、離 ATH 收盤 7 點，NDX 仍在 MA5 與 10/8 高之下的 inside day；SOXX 連兩日不跟；VXN 20.55 中波動 vs VIX 14.84 低波動。",
    "trades": [],
    "rejected_by_rule53": [
        {"name": "反彈空（10/9 高 30,947）", "order": "limit_sell", "entry": 30945, "stop": 31135, "t1": 30770, "dist_pct": 0.20, "rr_t1": 0.92,
         "reason": "rule53 中性全日不掛；即使可掛，rule52 停損 31,135（190 點）下 RR 0.92 <1.0 亦不掛。"},
        {"name": "回踩多（10/9 低 30,770）", "order": "limit_buy", "entry": 30770, "stop": 30546, "t1": 30947, "dist_pct": -0.37, "rr_t1": 0.79,
         "reason": "rule53 中性全日不掛；rule52 停損須在 10/8 低 30,556 之外（224 點）→ RR 0.79 <1.0。"},
    ],
    "rejected_by_rule27": [
        {"name": "破位空（收盤 < 30,556）", "order": "sell_stop_close_confirm", "entry": 30556, "dist_pct": -1.06, "reason": "rule53 中性全日不掛；距離 1.06% 亦超 rule27 門檻 0.625%。"},
        {"name": "突破多（10/8 高 31,125 之上）", "order": "buy_stop", "entry": 31130, "dist_pct": 0.80, "reason": "rule53 中性全日不掛；距離 0.80% 亦超 rule27 門檻 0.625%。"},
    ],
}
save("ndx_pnl_ledger.json", p)
open("ndx_update_1012.txt", "w", encoding="utf-8").write(
    f"OK graded={len(g)} h={hits} half={half} m={miss} score={score} neu={neu_pct} brier={b['mean_brier']} n={b['included']} flat={b['excluded_flat']} days={sm['days_evaluated']} "
    f"op={op_pts}/{op_ret}/{op_bp} rs={rs_pts}/{rs_ret}/{rs_bp} day={day} cum={cum} intraday={sm['cumulative_if_intraday_checked']} total={sm['trades_total']} filled={sm['trades_filled']} "
    f"win={sm['filled_win']} loss={sm['filled_loss']} fill_rate={sm['fill_rate_pct']} gap={sm['gap_invalidation_rate_pct']}\n")
