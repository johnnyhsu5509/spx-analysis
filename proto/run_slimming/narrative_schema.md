# 每日敘事 JSON 規格（SPX／NDX）

> 給接排程的人（Codex）用。模型每天只寫這一份 JSON，其餘由 `daily_run.py` 產生。
> 範例：`_work\merged_spx1022.json`（22.7KB）、`_work\merged_ndx1022.json`（16.8KB），是從 10/22 實跑反推的完整版本。

## 原則

1. **數字不要寫進敘事。** 收盤、A、區間、成交價、停損、勝率、Brier、累積 bp 都由腳本從帳本算；敘事裡出現的數字只能是「引用」（例如價位、新聞數字），不能是要記帳的值。
2. 敘事欄位沒寫就用預設模板，不會報錯；但 `html` 區塊裡標「必填」的沒寫會報錯。
3. 頂層區塊整段取代；`amplitude`、`predictions`、`backtest_prev`、`rule_status`（SPX），以及 NDX 的 `amplitude`、`volatility_scale`、`breadth`、`sector`、`regime_check`、`spx_cross_check`、`predictions`、`backtest_prev`、`position_level`，是「只覆蓋你給的鍵」。

## SPX

```jsonc
{
  "track": {                          // 方向帳與振幅帳的說明文字（選填，有預設）
    "grade_note": "…",                //   上一筆判定說明
    "bias": "…",                      //   新一筆的立場敘事
    "amp_note": "…"                   //   振幅帳說明
  },
  "pnl": {                            // 選填
    "day_note": "…", "honest_read": "…",
    "shadow_note_long": "…", "shadow_note_short": "…",
    "shadow_fill_time_et": {"short": "09:30"}   // 30 分 K 看到的成交時間，只影響說明
  },
  "last_analysis": {                  // 寫入 last_analysis.json 的敘事欄位
    "rating": "…", "news_check": {…}, "macro_layer": {…}, "sector_rotation": {…}, "breadth": {…},
    "regime_check": {…}, "six_factors": {…}, "catalysts": […], "event_week": {…},
    "amplitude": {"note": "…"},
    "predictions": {"short_bias", "key_resistance", "key_support", "fib_targets", "zhongshu", "elliott", "watch_points"},
    "backtest_prev": {"summary": "…"},
    "rule_status": {"rule1": "…", …}    // rule63／64／65／66／16／17 由腳本產生，不要寫
  },
  "rule_candidates_append": {"rule56": "｜10/21 不計…"},   // 只寫「要接在原文後面的字」
  "html": {
    "backtest_notes": ["…"],          // 必填：第一區說明框
    "deviation": "…",                 // 必填：偏差分析
    "amp_note": "…",                  // 必填：振幅說明（平靜期、事件日）
    "macro_title": "check_es，台北 10/22 08:33，亞洲薄盤", "macro_note": "…",
    "regime_labels": ["VIX 16-20（中波動，16.68）", "SPX 在 MA200 之上", "距 MA20 ±3% 內（+0.28%）"],
    "regime_warn": "…", "breadth_note": "…",
    "price_rows": [["K 線", "O … H … L … C …", "up", "讀法"], …],
    "granville": [["買① 轉升首穿", "<span class=\"up\">雛形</span>：…"], …],   // 8 格
    "chan_note": "…", "elliott_rows": [["① 5 浪進行中", "50%", "up", "路徑"], …], "bias_note": "…",
    "levels": [["7,757", "10/16 高／費波 0.382", "7,735", "MA20"], …],
    "notes_catalyst": "…", "notes_watch": "…",
    "ledger_kpi_notes": {…}, "nq_note": "…", "rates_note": "…", "fill_note": "…", "footer_note": "…",   // 選填
    "notes_support": "7,735 / 7,709 / 7,668", "notes_resistance": "…"                                // 選填，預設取 key_support／key_resistance 前三
  }
}
```

## NDX

```jsonc
{
  "track": {"note": "…", "sample_caveat": "…", "brier_honest_read": "…", "amp_note": "…"},   // 選填
  "pnl": {"day_note": "…", "honest_read": "…",
          "fill_type_long": "…", "fill_type_short": "…", "exit_type_long": "…", "exit_type_short": "…"},  // 選填
  "last_analysis": {
    "rating": "…", "data_quality": {…}, "catalysts": […], "news_check_rule49": "…", "candidate_updates": {…},
    "amplitude": {"note": "…"}, "volatility_scale": {"note": "…"},
    "breadth": {"read": "…"}, "sector": {"read": "…"}, "macro": {"read": "…"},
    "regime_check": {"alignment": "…"},
    "spx_cross_check": {"ndx": {"band": "…"}, "spx": {"band": "…"}, "verdict": "…"},
    "predictions": {"key_resistance", "key_resistance_note", "key_support", "key_support_note", "fib_targets",
                    "zhongshu", "elliott": {"main", "alt", "alt2"}, "scenarios_narrative", "granville", "watch_points"},
    "backtest_prev": {"actual": "…", "shadow": "…"}
  },
  "system_rules_notes_extra": ["rule36：…", "rule15：…"],    // rule55～59 由腳本產生
  "html": {
    "title": "…", "breadth_kpi": "…", "vxn_kpi": "…", "data_note": "…",
    "shadow_actual_long": "…", "shadow_actual_short": "…",
    "check_rows": [["29,749／29,862", "收上＝B 浪展開", "實際", "🟡 半成立", "nu"], …],
    "deviation": "…", "dims": [["廣度", "讀數", "判讀"], …], "amp_warn": "…",
    "regime_labels": ["18–28 中波動（24.42）", "MA200 之上 ", "±3% 內正常（-1.84%，由深跌檔換回）"],
    "ndx_band": "中波動檔", "spx_band": "16–20 檔", "cross_label": "【分歧】", "cross_note": "…",
    "news": "…", "news_sources": "Trading Economics、cappnotes、CNBC"
  }
}
```

## 腳本會擋下、要人工處理的情況

- 同一份收盤已分析過（等同 check_duplicate 的 DUPLICATE）
- amplitude 缺或過期（照 SKILL 寫「振幅資料缺」）
- 有實單 trades_pending、或方向偏離 50（原型只涵蓋 Phase 3 休眠期）
- NDX 部位水位切換或處於半倉（rule59 事件）
- NDX 跑的時候 SPX 當天還沒跑完（spx-last 的基準日不是今天）
