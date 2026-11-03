# 排程瘦身：記帳腳本與影子模式

每天的排程原本要手寫一支一次性記帳腳本（`spx_update_MMDD.py`、`ndx_ledger_MMDD.py`、`ndx_last_MMDD.py` 等），再手寫整份 HTML。
現在把固定公式收成 `scripts/` 下的參數化腳本，模型只需要寫當天的敘事 JSON。

**目前狀態：排程照舊，還沒接上。** 先跑 5 個交易日的影子模式，確認腳本和手寫記帳的數值一致，再改 SKILL。

## 腳本

| 腳本 | 做什麼 | 寫檔 |
|---|---|---|
| `scripts/spx_daily_mech.py` | SPX 三本帳（track_record／pnl_ledger 含 shadow_ledger／last_analysis 數值欄位） | 只有加 `--out` 才寫帳本 |
| `scripts/ndx_daily_mech.py` | NDX 兩本帳（ndx_track_record／ndx_pnl_ledger 含 shadow_ledger） | 只有加 `--out` 才寫帳本 |
| `scripts/ndx_last_mech.py` | `ndx_last_analysis.json`（SPX 的 A、VIX、regime 直接讀 SPX 當天的 last_analysis） | 只有加 `--out` 才寫 |
| `scripts/render_spx_html.py`／`render_ndx_html.py` | 兩份 HTML 報告，數字與表格由帳本產生，版型沿用前一份報告的 `<head>` | 寫 `--out` 指定的檔 |
| `scripts/daily_run.py` | 上面幾支串起來：記帳 → 渲染；加 `--out` 時同時寫 `spx/`、`ndx/` 的 `index.html`，從不碰 `docs/index.html` | 只有加 `--out` 才寫 |
| `scripts/shadow_check.py` | 影子比對：從 git 取分析 commit 前後的帳本，重算後逐欄比對 | 只寫比對報告，不寫帳本 |
| `scripts/mech_lib.py` | 共用函式（讀寫、判定 session、影子單成交、比對） | — |

只用 Python 標準庫，所有檔案讀寫都是 UTF-8（Windows 預設 cp950 也能跑）。報告預設寫在 `scripts/*.txt`，已被 `.gitignore` 排除。

## 影子模式（排程照舊，另跑腳本比對 5 個交易日）

不用寫敘事 JSON：`shadow_check.py` 直接拿實跑寫進帳本的敘事文字，只重算公式。每天排程 commit／push 完之後，在本機 repo 執行：

```bash
git pull
```

```bash
python scripts/shadow_check.py --symbol spx --since 2026-11-04 --all --report scripts/shadow_check_spx.txt
```

```bash
python scripts/shadow_check.py --symbol ndx --since 2026-11-04 --all --report scripts/shadow_check_ndx.txt
```

`--since` 填影子期第一天的報告日，之後每天重跑會把影子期內每次實跑一起重算（報告覆寫）。也可以直接給 commit：`python scripts/shadow_check.py --symbol spx <sha>`。

### 怎麼讀報告

每次實跑一段：`## spx <commit>（報告日 …，判定 …）：數值差異 N、字串差異 M、欄位有無 K`。

- **數值差異必須是 0。** 唯一的已知例外是 SPX `track_record.json:summary.brier.excluded_flat`（腳本 30、實跑 29）：實跑 10/28 判定 flat 時漏加這個欄位，之後每天照抄，帳本修正前每天都會出現。
- **字串差異**只會出在腳本產生的模板句（`note_latest`、`backtest_prev.shadow`、`rule66`、NDX 的 rule57／58／59 與 `backtest_prev.predicted`／`amp`、漂移基準說明）：實跑每天措辭不同，不影響帳。
- **輸入修正**：git 裡的 `data/` 快照（GitHub Actions 抓的）和本機實跑抓到的數據不同的欄位，以帳本記下的為準。這是說明，不算差異。當天的快照還沒進 git 時，會改用本機的 `scripts/today_data.txt`／`ndx_today_data.txt`（trade_date 要對得上）。
- 有數值差異時結束碼是 1。

每天把「數值差異」那一行記進 handoff_log。連續 5 個交易日除了上面那個已知例外都是 0，就可以進入上線步驟。有新的數值差異時，先判斷是手寫記帳錯、還是腳本錯，再決定修哪邊。

### 也可以跑單元測試

```bash
python -m unittest discover -s tests -p "test_run_slimming.py"
```

測試會從 git 重建 2026-10-20 起每一次 SPX／NDX 實跑，把每日差異表印到 stderr。影子期新增的實跑會自動納入；出現未說明的差異（例如新的數值差異）測試就會失敗。

## 上線後模型每天還要寫的部分

模型每天只寫一份敘事 JSON（加上 NDX 的 aux 數據），交給 `daily_run.py`：

```bash
python scripts/daily_run.py --symbol spx --docs docs --today scripts/today_data.txt --narrative narrative_MMDD.json --out docs
```

```bash
python scripts/daily_run.py --symbol ndx --docs docs --today scripts/ndx_today_data.txt --aux ndx_aux.json --narrative narrative_MMDD.json --out docs
```

敘事 JSON 的區塊（沒寫的欄位用預設模板；頂層區塊整段取代，`amplitude`、`predictions`、`backtest_prev`、`rule_status` 等只覆蓋給到的子鍵）：

- **SPX**
  - `track`：`grade_note`、`bias`、`amp_note`，gap day 另給 `gap_note`（接在原文後面）
  - `pnl`：`day_note`、`honest_read`、`shadow_note_long`／`short`，30 分 K 看到的 `shadow_fill_time_et`／`shadow_stop_time_et`（只影響說明）
  - `last_analysis`：`rating`、`news_check`、`macro_layer`、`sector_rotation`、`breadth`、`regime_check`、`six_factors`、`catalysts`、`event_week`、`amplitude.note`、`predictions`（`short_bias`、`key_resistance`、`key_support`、`fib_targets`、`zhongshu`、`elliott`、`watch_points`）、`backtest_prev.summary`（gap day 另給 `gap_day`）、`rule_status` 裡 rule63／64／65／66／16／17 以外的規則
  - `rule_candidates_append`：只寫要接在原文後面的字
  - `html`（必填）：`backtest_notes`、`deviation`、`amp_note`、`macro_title`、`macro_note`、`regime_labels`、`regime_warn`、`breadth_note`、`price_rows`、`granville`、`chan_note`、`elliott_rows`、`bias_note`、`levels`、`notes_catalyst`、`notes_watch`
- **NDX**
  - `track`：`note`、`sample_caveat`、`brier_honest_read`、`amp_note`、gap day 的 `gap_note`
  - `pnl`：`day_note`、`honest_read`、`fill_type_long`／`short`、`exit_type_long`／`short`、gap day 的 `gap_note`
  - `last_analysis`：`rating`、`data_quality`、`catalysts`、`news_check_rule49`、`candidate_updates`、各區塊的說明句（`amplitude.note`、`volatility_scale.note`、`breadth.read`、`sector.read`、`macro.read`、`regime_check.alignment`、`spx_cross_check` 的 `band`／`verdict`）、`predictions`（價位、波浪、情景、觀察點）、`backtest_prev.actual`／`shadow`（含 30 分 K 的時間）
  - `system_rules_notes_extra`：rule55～59 以外的規則註記
  - `html`（必填）：`title`、`breadth_kpi`、`vxn_kpi`、`data_note`、`deviation`、`dims`、`amp_warn`、`regime_labels`、`ndx_band`、`spx_band`、`cross_label`、`cross_note`、`news`、`news_sources`
  - `--aux`（當天另外量的數據，原樣搬進對應區塊）：`{"volatility_scale": {"atr14_pct", "range5_pct", …}, "breadth": {"qqqe_qqq_ratio", "chg_1d_pct", …}, "sector": {"soxx_close", …}, "macro": {"tnx", "vix", "vxn", "dxy", …}}`

**數字不要寫進敘事。** 收盤、A、區間、成交價、停損、勝率、Brier、累積 bp 都由腳本從帳本算。

## 腳本會擋下、要人工處理的情況

- 同一份收盤已分析過（等同 `check_duplicate.py` 的 DUPLICATE）
- amplitude 缺、`stale` 或 `as_of` 不是當天（照 SKILL 寫「振幅資料缺」）
- 有實單（SPX `trades_pending`、NDX `trades_pending.trades`），或方向偏離 50：腳本只涵蓋 Phase 3 休眠期
- 待判定預測的目標日不在 today_data 的 `recent_5` 裡（連續漏跑超過 3 個交易日）
- NDX 部位水位（rule59）切換或處於半倉
- NDX 跑的時候 SPX 當天還沒跑完
- HTML 敘事缺必填欄位

gap day（例如 10/26：前一個收盤沒做分析）會自動處理：待判定預測照常用目標日的 OHLC（取自 `recent_5`）判定，gap day 寫進各 `summary.gap_days`。
美股假日不會自動跳過（`next_bday` 只跳週末），假日前一天要加 `--report-date`。

## 上線步驟（都不在這次的改動裡）

1. 影子模式 5 個交易日：排程照舊，每天跑 `shadow_check.py`，結果記進 handoff_log。
2. 沒有新的數值差異 → 改 SPX／NDX SKILL 的 Step 2／5／6：寫敘事 JSON → 跑 `daily_run.py --out docs` → 讀報告確認 → commit／push。
3. 依慣例交 Codex 做隔離驗收。

另外兩件可以順手處理、但這次沒動：帳本 `excluded_flat` 的修正（要改 `docs/`），以及 `track_record.summary` 每天新增一個 `always_neutral_baseline_YYYYMMDD` 鍵（改成單一鍵每天覆寫，屬帳本格式變更）。
