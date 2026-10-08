import json

D = "../docs/"


def load(n):
    return json.load(open(D + n, encoding="utf-8"))


def save(n, o):
    json.dump(o, open(D + n, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


t = load("ndx_track_record.json")
e = t["entries"][-1]
assert e["report_date"] == "2026-10-07" and e["grade"] == "pending"
assert not any(x["report_date"] == "2026-10-08" for x in t["entries"])
e.update({
    "actual_date": "2026-10-07", "actual_pct": -0.21, "actual_dir": "flat", "grade": "hit",
    "note": "10/7 開 30,976.25（跳空 -0.80%）→ 低 30,904.46（09:30 棒）→ 尾盤拉回 → 收 31,160.08（-0.21%）→ **flat**。預測中性 54% 遇 flat → **hit**。Brier：flat 排除。\n\n"
            "【情景 B（39%）實現】收盤落在 31,100–31,350。盤中回補 31,117–31,208 缺口並下探 30,904，未觸及 30,798 第三類買點低點；收在區間 96%、實體 +184 的長紅 K。\n\n"
            "【當日】FOMC 9 月紀要偏鷹、10Y 盤中約 5.31%（收 5.277%）、Brent 約 101；SOXX -1.12%、QQQE -0.89%，指數靠權值收回。",
})
t["entries"].append({"report_date": "2026-10-08", "basis_close": 31160.08, "basis_date": "2026-10-07",
                     "pullback_prob": 55, "bias": "中性偏空", "actual_date": None, "actual_pct": None,
                     "actual_dir": None, "grade": "pending"})
g = [x for x in t["entries"] if x.get("grade") in ("hit", "half", "miss")]
hits = sum(x["grade"] == "hit" for x in g); half = sum(x["grade"] == "half" for x in g); miss = sum(x["grade"] == "miss" for x in g)
score = round((hits + half * 0.5) / len(g) * 100, 1)
neu = [1.0 if x["actual_dir"] == "flat" else 0.5 for x in g]
neu_pct = round(sum(neu) / len(neu) * 100, 1)
s = t["summary"]
s.update({"as_of": "2026-10-08", "graded": len(g), "hits": hits, "half": half, "miss": miss,
          "rolling_direction_score_pct": score,
          "always_neutral_baseline_pct": neu_pct,
          "sample_caveat": f"n={len(g)}。{score}% ＝ ({hits} hit + {half} half×0.5 + {miss} miss) / {len(g)}。always-neutral 基準 {neu_pct}%（依 audit_20261002 須並列）。"})
b = s["brier"]
b["per_entry"].append({"report_date": "2026-10-07", "p": 0.54, "outcome": "flat_excluded", "brier": None})
vals = [x["brier"] for x in b["per_entry"] if x["brier"] is not None]
b["included"] = len(vals)
b["excluded_flat"] = sum(1 for x in b["per_entry"] if x["brier"] is None)
b["mean_brier"] = round(sum(vals) / len(vals), 4)
b["as_of"] = "2026-10-08"
b["honest_read"] = f"mean brier **{b['mean_brier']}**（n={b['included']}），與 0.25 基準相當。10/7 報 54 遇平 -0.21%，flat 排除不計。"
save("ndx_track_record.json", t)

p = load("ndx_pnl_ledger.json")
assert p["trades_pending"]["report_date"] == "2026-10-07"
assert not any(x["report_date"] == "2026-10-07" for x in p["entries"])
p["entries"].append({
    "report_date": "2026-10-07", "basis_close": 31224.69, "eval_date": "2026-10-07",
    "eval_ohlc": {"open": 30976.25, "high": 31170.12, "low": 30904.46, "close": 31160.08},
    "rule50_check": "rule53 全日不掛，無單可判。",
    "rule51_check": "無成交單，不需判序。",
    "trades": [],
    "day_weighted_bp": 0.0,
    "shadow_rejected": "【僅揭露、不計帳】被 rule53 擋下的單：回踩多 limit_buy 31,120 跳空開在 30,976 成交（低於掛單價），09:30 棒低 30,906.6 同棒跌破停損 30,920 → 約 -0.18%；反彈空 31,400、突破多 31,370 未觸發；破位空收盤 31,160 > 31,100 未觸發。",
    "day_note": "rule53 全日不掛 → 當日 **0bp**。累積維持 **-3.95bp**。",
})
sm = p["summary"]
sm.update({"as_of": "2026-10-08", "days_evaluated": sm["days_evaluated"] + 1,
           "cumulative_weighted_bp": -3.95,
           "honest_read": "累積維持 **-3.95bp**（30 分 K 揭露口徑 -6.24bp）。rule52／53 生效後連四日（10/5–10/7 報告）中性全日不掛；影子帳 10/5 擋下約 -0.74bp、10/6 擋下兩張小賺單、10/7 擋下回踩多（差 13 點未掃停損，收盤約 +0.59%）→ 新制影子帳目前略為少賺。10/8 報告首度有順 lean 空單可掛。成交 21 筆 7 勝 14 敗。"})
p["trades_pending"] = {
    "report_date": "2026-10-08", "basis_close": 31160.08,
    "eval_rule": "用 2026-10-08 美股 NDX OHLC 判定。limit_sell 開盤 ≥ 停損 → GAP_INVALIDATED（prc-004）；同日成交與觸價以 30 分 K 判序（rule51）。close-confirm 以收盤 < 31,035 成交，T1／T2／停損依 prc-003 浮動（ATR14 1.199%）。",
    "signal_atr14_pct": 1.199,
    "divergence_check": "NDX 55 中性偏空 vs SPX 47 中性（全日不掛）→ 分歧，NDX 側倉位已減半。regime：VXN 中波動 +1.5pp vs SPX VIX<16 -6.2pp → 波動檔分歧持續。",
    "trades": [
        {"name": "反彈空（缺口上緣／前收盤高 31,208–31,225）", "order": "limit_sell", "entry_signal": 31220, "dir": "short",
         "stop": 31410, "t1": 30980, "t2": 30800, "dist_pct": 0.19, "rr_t1": 1.26, "rr_t2": 2.21, "weight": 4,
         "note": "rule52：停損 max(0.5×ATR 187 點, 31,361 歷史高之上) → 31,410（190 點）。RR 1.26 → 倉位減半。"},
        {"name": "破位空（收盤 < 31,035）", "order": "sell_stop_close_confirm", "entry_signal": 31035, "dir": "short",
         "t1_reference": 30663, "t2_reference": 30291, "stop_reference": 31407, "dist_pct": -0.40, "weight": 5,
         "note": "prc-003 浮動：T1＝成交價−0.8×ATR、T2＝−1.6×ATR、停損＝+0.8×ATR（ATR14 1.199%）。參考價以 31,035 試算。"},
    ],
    "rejected_by_rule53": [
        {"name": "回踩多（30,910 當日低）", "order": "limit_buy", "entry": 30910, "dist_pct": -0.80,
         "reason": "逆 lean（bias 中性偏空）weight 0；且距離 0.80% 超 rule27 門檻 0.624%。"},
        {"name": "突破多（31,370 歷史高之上）", "order": "buy_stop", "entry": 31370, "dist_pct": 0.67,
         "reason": "逆 lean weight 0；超 rule27 門檻；QQQ 量 75.9% 未帶量。"},
    ],
    "rejected_by_rule27": [
        {"name": "破位空（收盤 < 30,904 當日低）", "order": "sell_stop_close_confirm", "entry": 30900, "dist_pct": -0.83,
         "reason": "距離 0.83% 超 rule27 門檻 0.624%。"},
    ],
}
save("ndx_pnl_ledger.json", p)
open("ndx_update_1008.txt", "w", encoding="utf-8").write(f"OK graded={len(g)} score={score} neu={neu_pct} brier={b['mean_brier']} n={b['included']} days={sm['days_evaluated']}\n")
