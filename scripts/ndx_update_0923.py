import json

D = "../docs/"


def load(n):
    return json.load(open(D + n, encoding="utf-8"))


def save(n, o):
    json.dump(o, open(D + n, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# ---------- track record ----------
t = load("ndx_track_record.json")
e = t["entries"][-1]
assert e["report_date"] == "2026-09-22" and e["grade"] == "pending"
e.update({
    "actual_date": "2026-09-22", "actual_pct": 0.82, "actual_dir": "up", "grade": "half",
    "note": "9/22 開 30,496.43 → 高 30,770.63 → 低 30,496.43 → 收 30,732.40（+0.82%）→ **up**。預測中性 51% 遇 up → **half**。Brier (0.51-0)² = 0.2601。\n\n"
            "【情景 A（31%）實現】收盤站上歷史收盤高 30,661，盤中高 30,770.63 亦超越 6/3 的 30,762.20，**NDX 本身正式創收盤與盤中雙新高**。\n\n"
            "【51 的代價】真正的中性遇到方向日必然拿 half，Brier 略高於基準（0.2601 vs 0.25）。這是報中性該付的成本，不是錯判。",
})
t["entries"].append({"report_date": "2026-09-23", "basis_close": 30732.4, "basis_date": "2026-09-22",
                     "pullback_prob": 52, "bias": "中性", "actual_date": None, "actual_pct": None,
                     "actual_dir": None, "grade": "pending"})
s = t["summary"]
s.update({"as_of": "2026-09-23", "graded": 18, "hits": 8, "half": 7, "miss": 3,
          "rolling_direction_score_pct": 63.9,
          "sample_caveat": "n=18。63.9% ＝ (8 hit + 7 half×0.5 + 3 miss) / 18 = 11.5/18。"})
b = s["brier"]
b["per_entry"].append({"report_date": "2026-09-22", "p": 0.51, "outcome": 0, "brier": 0.2601})
inc = [x for x in b["per_entry"] if x["brier"] is not None]
mean = round(sum(x["brier"] for x in inc) / len(inc), 4)
b.update({"as_of": "2026-09-23", "included": len(inc), "mean_brier": mean,
          "honest_read": f"mean brier 0.2384 → **{mean}**（n={len(inc)}），仍低於基準 0.25。9/22 報中性 51% 遇 up，Brier 0.2601 略高於基準——中性報價在方向日的固定成本。"})
save("ndx_track_record.json", t)

# ---------- pnl ledger ----------
p = load("ndx_pnl_ledger.json")
tp = p["trades_pending"]
assert tp["report_date"] == "2026-09-22"
p["entries"].append({
    "report_date": "2026-09-22", "basis_close": 30482.35, "eval_date": "2026-09-22",
    "eval_ohlc": {"open": 30496.43, "high": 30770.63, "low": 30496.43, "close": 30732.4},
    "rule50_check": "反壓空開盤 30,496.43 < 停損 30,820 → 未跳空穿越，正常判定。",
    "trades": [{
        "name": "反壓空", "order": "limit_sell", "entry_signal": 30660, "dir": "short", "weight": 4,
        "signal_triggered": True, "filled": True,
        "status": "FILLED → 停損與目標皆未觸及，收盤平倉",
        "fill_price": 30660, "exit_price": 30732.4,
        "exit_reason": "收盤平倉（高 30,770.63 未及停損 30,820，差 49.37 點；低 30,496.43 未及 T1 30,482）",
        "pts": -72.4, "ret_pct": -0.2361, "weighted_bp": -0.94,
        "intraday_check": "30 分 K：10:00 棒高 30,679.5 首次觸及 30,660 成交；成交後最低 30,590.7（12:00 棒），未回到 T1 30,482。日線與 30 分 K 判定一致，prc-006 不影響本筆。",
    }],
    "day_weighted_bp": -0.94,
    "day_note": "反壓空成交後收盤平倉 -72.4 點 → 當日 **-0.94bp**。累積 -2.62 → **-3.56bp**。",
    "honest_note": "在歷史高點上做均值回歸，遇到的是突破日。停損設在歷史盤中高之上的 30,820 讓這筆只小虧；**若停損貼著 30,762 設，就會被掃掉**。",
})
sm = p["summary"]
sm.update({"as_of": "2026-09-23", "days_evaluated": 18, "trades_total": 35, "signals_triggered": 18,
           "trades_filled": 16, "filled_loss": 11, "fill_rate_pct": round(16 / 35 * 100, 1),
           "gap_invalidation_rate_pct": round(2 / 18 * 100, 1), "cumulative_weighted_bp": -3.56,
           "cumulative_if_intraday_checked": -5.85,
           "honest_read": "累積 -2.62 → **-3.56bp**（現行日線規則）；30 分 K 核對口徑 -4.91 → **-5.85bp**。9/22 反壓空遇突破日小虧 -0.94bp。成交 16 筆 5 勝 11 敗。"})
ATR = 1.231
p["trades_pending"] = {
    "report_date": "2026-09-23", "basis_close": 30732.4,
    "eval_rule": "用 2026-09-23 美股 NDX OHLC 判定；適用 rule50（prc-004）。**prc-006 仍待核准，照日線規則記帳，另以 30 分 K 揭露。**",
    "signal_atr14_pct": ATR,
    "divergence_check": "【rule49】NDX 52 vs SPX 51 同側 → 數字同向，不減半；但結構相反（NDX 突破歷史高、SPX 測壓失敗、regime 超額 +1.5 vs -6.2），倉位本身已壓低。",
    "trades": [
        {"name": "回踩多（舊歷史收盤高轉支撐）", "order": "limit_buy", "entry": 30661, "stop": 30480, "t1": 30960, "t2": 31040,
         "weight": 4, "dir": "long",
         "condition_note": "錨定 6/2 歷史收盤高 30,660.60（突破後回測）。停損置於 9/22 全日低 30,496 之下，181 點＝0.48 ATR。T1＝可執行帶上緣、T2＝進場＋1 預期振幅。RR 1.65／2.09。"},
        {"name": "突破多（新盤中高之上）", "order": "buy_stop", "entry": 30775, "stop": 30640, "t1": 30960, "t2": 31040,
         "weight": 3, "dir": "long",
         "condition_note": "9/22 盤中高 30,770.63 之上。三條件：QQQ 123.1% ≥ 115.5% ✓、MACD 柱 +77 → +135 擴大 ✓、價格在所有均線之上 ✓。停損回到舊高 30,661 之下。RR 1.37／1.96。過熱中追價，倉位最小。"},
        {"name": "破位空（收盤確認）", "order": "sell_stop_close_confirm", "entry": 30590, "weight": 3, "dir": "short",
         "t1_reference": 30289, "t2_reference": 29987, "stop_reference": 30891,
         "condition_note": "收盤跌破 9/22 盤中雙底 30,591／30,590.7 才成立。浮動目標（prc-003）：T1＝成交−0.8 ATR、T2＝成交−1.6 ATR、停損＝成交＋0.8 ATR，ATR14＝1.231%。參考值以 30,590 成交估算。"},
    ],
    "rejected_by_rule27": [
        {"name": "回踩多（8/17 高轉支撐 30,196）", "entry": 30196, "dist_pct": -1.75, "threshold": 0.74, "reason": "超過門檻。"},
        {"name": "反壓空", "entry": None, "reason": "歷史新高之上無可驗證的結構壓力，不在未知區域硬造壓力。"},
    ],
}
save("ndx_pnl_ledger.json", p)
open("ndx_update_0923.txt", "w", encoding="utf-8").write(f"OK mean_brier={mean} n={len(inc)}\n")
