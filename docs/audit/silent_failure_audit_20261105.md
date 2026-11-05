# 靜默失敗稽核報告（2026-11-05）

> 唯讀稽核，**沒有改任何程式、資料或帳本**。本文件只列問題與建議修法，修不修、怎麼修另行決定。

## 0. 範圍與方法

**範圍**：`scripts/fetch_today.py`、`scripts/check_es.py`、`scripts/check_open30.py`、`scripts/check_duplicate.py`，以及它們 import 的本 repo 模組：`guard.py`、`gap_fix.py`、`wilder.py`、`cme_session.py`、`yf_compat.py`。

**只找三類**：

1. 缺資料／抓取失敗被當正常值（0、空、中性、預設值、沿用舊值未標 stale／SNAPSHOT），或過舊資料仍被接受
2. 例外被吞掉（`except: pass`、失敗仍 exit 0、只 print 不中止）
3. 指數路由（沒加或打錯 `--symbol`、NDX 讀寫到 SPX 檔、檔名與 symbol 欄位不一致、check_duplicate 比對錯檔）

**方法**：

- 用 `tests/harness.py` 的假 yfinance stub（全程不連網），在暫存樹執行腳本、讀輸出檔。
- `harness.MODULES` 不含 `check_open30.py`、`check_duplicate.py`，所以重現腳本在執行期把這兩支加進 `MODULES`／`OUTPUTS`，`tests/` 本身沒改。
- `check_duplicate.py` 直接 `import guard`，沒有先把 sys.path 指到 scripts/，經 `runpy` 執行會 ImportError。因此改成在暫存樹裡用 `python3 scripts/check_duplicate.py` 直接跑（它不需要 yfinance stub）。
- 每條標示 **已重現**（stub 跑出輸出）或 **推測**（讀碼推論，或影響發生在範圍外的 workflow／SKILL）。
- 重現腳本全文在附錄 A，可以原樣再跑一次。

**已知且已處理、不重報**：fetch 失敗不寫檔並 exit 1、check_es 的 `data_status=ALL_FAILED`（全掛時移除 `macro_backdrop`）、`WEEKEND_CLOSED`、`sector_daily` 缺值為 null 並列入 `stale`。

## 1. 總表

| 編號 | 嚴重度 | 位置 | 類別 | 狀態 | 一句話 |
|---|---|---|---|---|---|
| H1 | 高 | check_es.py:80,95,182,248 | 1 | 已重現 | 報價為 NaN 時被讀成 NEUTRAL／FLAT，`data_status=OK`、合成分「MIXED 中性」 |
| H2 | 高 | check_duplicate.py:34-38,49,58 | 1+2 | 已重現 | `last_analysis.json` 缺檔或損毀時 VERDICT=OK「safe to run full analysis」 |
| H3 | 高 | check_duplicate.py:49,52-53,58 | 1 | 已重現 | 只用子字串比對 `data_basis`；trade_date 比已分析日還舊、或帳本已有該日 entry，都回 OK |
| H4 | 高 | fetch_today.py:75-92,299-300 | 1+2 | 已重現（Actions 影響為推測） | 快照退回不檢查年齡、檔內沒有 SNAPSHOT 標記、exit 0；Actions 下會把舊快照重新 commit，並刷新 `fetched_at.txt` |
| H5 | 高 | fetch_today.py:339,392-393 | 1 | 已重現 | VIX/VXN 缺值寫成 `0`，判成「低波動」；末日 NaN 時沿用前一日的值，未標 stale |
| H6 | 高 | fetch_today.py:321-332,351 | 1 | 已重現 | 中間列 Close 為 NaN 時被 dropna 靜默刪除（gap_fix 在 dropna 之前跑），prev_close 錯接，沒有 data_integrity |
| H7 | 高 | check_open30.py:60,137-140 | 1 | 已重現 | 不檢查 `session_date` 是否為今日；美股未開盤時回傳前一日的首 30 分並 exit 0 |
| H8 | 高 | check_es.py:52-70,163-175 | 1 | 已重現 | 時段標籤寫死「台灣牆鐘＋美國夏令」，冬令與 Actions（UTC）都標錯；US_PREOPEN 時把前一日的 SOXX 當即時，算出假背離 |
| M1 | 中 | check_es.py:151-157,159-177 | 2 | 已重現 | NQ／SOXX 失敗時 `except: pass`，不留 `_error`，`data_status` 仍為 OK，合成分缺項當 0 |
| M2 | 中 | check_es.py:103-148 | 1+2 | 已重現 | 隱含開盤整段 `except: pass`：資料檔缺失時欄位消失但仍 OK；資料檔過舊時拿舊收盤套 pct_fallback，未標 stale |
| M3 | 中 | check_es.py:266-279 | 1 | 已重現 | ALL_FAILED 退回快照時不檢查年齡，而且覆寫掉快照原本的 `data_status`（PARTIAL 被抹掉） |
| M4 | 中 | check_open30.py:107-125,127-131 | 2 | 已重現 | 類股同步、波動指數逐一 `except: pass`；全缺時沒有 sector_sync、也沒有任何標記，仍 exit 0；輸出沒有 SKILL 要求看的 `data_status` |
| M5 | 中 | check_open30.py:47-51,63-72,84,124-125 | 1 | 已重現 | 30m K 未 dropna：首根 Close NaN → FLAT →「SYNC 訊號有效」；末根 NaN → current_price 為 NaN 仍 OK |
| M6 | 中 | gap_fix.py:38-59,76-77 | 2 | 已重現 | 30m 抓不到時缺日不補也不報，fetch_today 輸出沒有任何 data_integrity |
| M7 | 中 | fetch_today.py:402-407 | 1+2 | 已重現 | baseline 檔損毀或缺 key 時靜默改用內建 DEFAULT_C，輸出沒有來源標記 |
| M8 | 中 | fetch_today.py:57-66 等四支 | 3 | 已重現 | 打錯旗標、缺值、位置參數一律被忽略 → 預設 SPX，exit 0 |
| M9 | 中 | fetch_today.py:514-526 | 1 | 已重現 | 正常抓取路徑沒有 trade_date 新鮮度檢查，兩個月前的收盤也回報 OK |
| L1 | 低 | fetch_today.py:75-92,532 | 3 | 已重現 | 快照路徑不驗快照的 symbol，也跳過 cross_check（下游 guard 會擋） |
| L2 | 低 | check_duplicate.py:95 | 2 | 已重現 | NO_DATA／DUPLICATE 也 exit 0 |
| L3 | 低 | fetch_today.py:150-151,203-204 | 2 | 已重現 | breadth 例外或序列不足時回 None，沒印原因 |
| L4 | 低 | fetch_today.py:302,310；check_duplicate.py:63,73 | 3 | 已重現 | NDX 執行時，錯誤訊息與標籤仍寫 `today_data.txt` |
| L5 | 低 | check_es.py:263-264；check_open30.py:133-134 | 3 | 已重現 | 兩支的輸出檔沒有 `symbol` 欄位，無法驗來源 |
| L6 | 低 | gap_fix.py:30-35 | 2 | 已重現 | `manual_ohlc_overrides.json` 損毀時靜默忽略人工覆寫值 |
| L7 | 低 | cme_session.py:11-15 | 1 | 已重現（影響為推測） | 不處理 CME 假日與每日維護時段，假日的結算值被當即時 |

**合計：高 8、中 9、低 7。**

---

## 2. 高

### H1　check_es：NaN 報價被讀成「中性」，data_status=OK

- **位置**：`scripts/check_es.py:80`（`if last and prev:`）、`:95`（signal 判定）、`:182`（VIX）、`:189-192`（10Y）、`:201-202`（DXY）、`:248`（`_have_vix = ... is not None`）
- **觸發情境**：yfinance 的 `fast_info["last_price"]` 回傳 NaN。這在 Yahoo 限流、盤前未報價、或新合約剛換月時都會出現。`float('nan')` 是 truthy，所以 `if last and prev` 直接放行，不會走 history 備援。
- **實際輸出**（stub：所有報價 last=NaN）：
  ```
  data_status = "OK"
  es    = {"last": NaN, "change_pct": NaN, "signal": "NEUTRAL"}
  vix   = NaN
  us10y = {"yield_pct": NaN, "change_bps": NaN, "signal": "FLAT"}
  dxy   = {"last": NaN, "change_pct": NaN, "signal": "FLAT"}
  macro_backdrop = {"score": 0, "read": "MIXED 中性"}
  exit 0, stdout "OK data_status=OK"
  ```
  這正是 2026-08-13 ALL_FAILED 修正要防的「缺資料讀成中性」，只是換了 NaN 這條路進來。另外檔案裡寫出的 `NaN` 不是合法 JSON，非 Python 的解析器會直接讀不進去。
- **應有行為**：NaN 等同抓取失敗。該指標寫 `*_error`，計入 PARTIAL 或 ALL_FAILED，不得產生 signal，也不得參與合成分。
- **嚴重度**：高
- **建議修法**：在 `get_last_prev` 用 `math.isfinite(last) and math.isfinite(prev) and prev != 0` 取代 truthy 判斷；不通過就走 history 備援，history 也要先 `dropna(subset=["Close"])`。最後仍非有限值就 raise，交給既有的 `*_error` 分支處理。`_have_vix`／`_have_es`／`_have_10y` 也改成檢查有限值。寫檔時改用 `json.dump(..., allow_nan=False)` 當最後一道保險。

### H2　check_duplicate：帳本讀不到時回 OK

- **位置**：`scripts/check_duplicate.py:34-38`（`load()` 吞例外回傳 `{'__error__': ...}`）、`:46-49`、`:57-58`（verdict 只看 td 有沒有 `__error__`）
- **觸發情境**：`docs/last_analysis.json`（或 `ndx_last_analysis.json`）缺檔、合併衝突留下標記、JSON 損毀。git 衝突或半寫入都可能造成。
- **實際輸出**（已重現）：
  ```
  D1 last_analysis.json corrupt  exit=0 VERDICT: OK | MEANING: new close detected, safe to run full analysis.
  D1 last_analysis.json missing  exit=0 VERDICT: OK | MEANING: new close detected, safe to run full analysis.
  ```
  `track_record.json`、`pnl_ledger.json` 損毀時，同樣只會讓「last 3」那一行變空白，不影響 verdict。
- **應有行為**：防重複的依據讀不到，就不能判 OK。應給 `VERDICT: LEDGER_UNREADABLE`（或沿用 NO_DATA），提示 STOP，並 exit 非 0。
- **嚴重度**：高。重複寫帳無法回溯修復（guard.py 的 docstring 自己也這樣寫）。
- **建議修法**：`la`／`tr`／`pl` 任一含 `__error__` 時另立 verdict 並中止；`load()` 在缺檔與解析失敗時印出檔名與錯誤。

### H3　check_duplicate：只用子字串比對 data_basis，舊資料與帳本已有的日期都放行

- **位置**：`scripts/check_duplicate.py:49`（`trade_date in str(data_basis)`）、`:52-55`（tr／pl 日期只拿來顯示）、`:58`
- **觸發情境**：
  - (a) `today_data.txt` 的 trade_date 比上次已分析的還舊，例如 H4 的舊快照、或 Yahoo 撤回最新一列；
  - (b) `last_analysis.json` 被 revert 或回滾，但 track_record／pnl_ledger 已經有後續 entry。
- **實際輸出**（已重現）：
  ```
  D2  trade_date 2026-10-30，last_analysis.data_basis="2026-11-04 US close" → exit=0 VERDICT: OK（"new close detected"）
  D2b last_analysis 回滾到 "2026-11-03 US close"，兩本帳 last 3 已含 2026-11-04、2026-11-05
      today trade_date=2026-11-04 → exit=0 VERDICT: OK
  ```
- **應有行為**：
  - (a) trade_date ≤ 上次已分析的 trade_date 時，不得回 OK，應回 `STALE`（或至少 DUPLICATE）；
  - (b) 帳本的最新 report_date 已經晚於 last_analysis 對應的日期時，應判定三本帳不一致並 STOP。
- **嚴重度**：高
- **建議修法**：從 data_basis 解析出日期（目前格式是 `YYYY-MM-DD US close`），用日期大小比較，不要用子字串。另外交叉檢查 `tr_dates[-1]`、`pl_dates[-1]` 與 `last_analysis.trade_date` 是否一致，不一致就給獨立的 verdict。

### H4　fetch_today：快照退回不檢查年齡、檔內無標記、exit 0

- **位置**：`scripts/fetch_today.py:75-92`（`_use_snapshot`）、`:299-300`、`:307-308`、`:334-335`
- **觸發情境**：live 抓取拋例外、回空表、或全列 NaN，且 `data/<outfile>` 存在。
- **實際輸出**（stub：fetch 全拋例外，快照 trade_date=2026-10-01）：
  ```
  exit=0
  stdout: OK trade_date=2026-10-01 close=6500.0 (SNAPSHOT from data/, fetched_at=2026-11-05T01:29:08Z)
  scripts/today_data.txt：與快照逐位元相同；沒有 snapshot／stale／data_status 任何欄位
  ```
  1. **年齡**：只檢查 `trade_date` 存在與否，一個月前的快照也照用。
  2. **標記只在 stdout**：檔案本身與正常抓取的結果無法區分。下游的 check_duplicate、check_es 的隱含開盤、daily_run 讀到的都是「看似當日」的檔案。
  3. **Actions 回收（推測，依 `.github/workflows/fetch-data.yml` 推論）**：runner 上 checkout 後 `data/today_data.txt` 一定存在。所以 Yahoo 擋 runner 時，`fetch_today.py` 會退回舊快照並 exit 0（step 名稱寫「fails loudly if Yahoo blocks」，實際上不會 fail）。接著 copy step 把舊資料拷回 `data/`，`fetched_at.txt` 刷成當下時間，然後 commit「data: market snapshot <今天>」。之後雲端 session 退回快照時，印出的 `fetched_at` 是新的，資料卻是舊的。
- **應有行為**：退回快照時，檔內必須帶 `"data_source": "SNAPSHOT"`、`snapshot_fetched_at`，以及與預期交易日的落差。快照過舊（例如落後超過 1 個交易日）時不得 exit 0。在 Actions 環境不應退回快照。
- **嚴重度**：高
- **建議修法**：
  - `_use_snapshot` 不要直接 `shutil.copy`，改為讀入後加上標記欄位再寫出；
  - 依 trade_date 與今日（紐約時區）的營業日差距決定是否接受；
  - 偵測 `GITHUB_ACTIONS=true`（或加 `--no-snapshot` 參數）時停用快照退回，讓 workflow 真的失敗；
  - workflow 的 `fetched_at.txt` 應只在 live 成功時更新。這部分超出本次範圍，僅列為建議。

### H5　fetch_today：VIX/VXN 缺值寫成 0，末日缺值沿用前一日

- **位置**：`scripts/fetch_today.py:339`（`raw_vix.dropna`）、`:392-393`（`vix_val = ... if not vix_close.empty else 0`）、`:415-420`（regime）
- **觸發情境**：
  - (a) 波動指數整段 Close 為 NaN 或回空表，但指數本身正常；
  - (b) 波動指數最新一列 Close 為 NaN。這和 rule51 描述的 ETF 尾端 NaN 是同一種 Yahoo 機制。
- **實際輸出**（已重現）：
  ```
  (a) exit=0  vix = 0
      regime.vix = {"regime": "VIX<16（低波動）", "pullback_5d": 50.0, "vs_base": -10.0}
      amplitude = null（只在 stdout 印一行 WARNING）
  (b) exit=0  vix = 17.87（= 前一日值；當日實際 18.13）
      頂層 vix 沒有 stale 標記；只有 amplitude.stale=True
  ```
  (a) 會讓 regime 的 5D／1D 拉回率被系統性低估（被歸到最低波動桶）。
- **應有行為**：
  - (a) 波動指數缺值時不能寫 0。應寫 null 並讓 regime 的波動分項為 null，或直接 FETCH FAILED；
  - (b) 波動指數末日 ≠ 指數 trade_date 時，應加 `vix_as_of` 與 stale 標記，比照 breadth 的 rule51。
- **嚴重度**：高
- **建議修法**：比照 `_breadth` 的末日對齊檢查：用 `raw_vix.index[-1]` 對 trade_date，不一致時先試 30m 末根補值，補不到就標 stale；空序列一律視為失敗，不得用 `0` 當預設值。`_bad` 完整性檢查清單要加入 `VOL_KEY`。

### H6　fetch_today：中間列 Close 為 NaN → 靜默缺日、prev_close 錯接

- **位置**：`scripts/fetch_today.py:321-323`（gap_fix）在 `:328-332`（dropna）之前執行；`:351`（`prev_close = iloc[-2]`）
- **觸發情境**：Yahoo 某個非最新列的 Close 為 NaN（OHLV 其他欄位存在）。gap_fix 看該日「有列」，不認為缺日；接著 dropna 把它刪掉，序列就少了一天。
- **實際輸出**（stub：倒數第 2 列 Close=NaN）：
  ```
  exit=0
  stdout: [fetch] dropped 1 unsettled row(s) with NaN Close (Yahoo partial data)
  prev_close = 9179.77（= 倒數第 3 日收盤；正確前收 9150.42）
  change_pct = 1.09（錯）
  data_integrity = null
  ```
  stdout 的訊息說的是「未結算列」，暗示被丟的是最新一列，實際被丟的卻是前一交易日。MA／RSI／MACD／KD 也都錯位一天，和 2026-08-28 事件是同一類後果。
- **應有行為**：只有「最新一列」可以當作未結算而丟棄。中間列 NaN 應交給 gap_fix 從 30m 回補，補不到就 FETCH FAILED，或在 data_integrity 標明缺日。
- **嚴重度**：高
- **建議修法**：先 dropna 再呼叫 `gap_fix.patch_missing_days`，讓被刪的中間列變成「缺日」，再由 30m 回補並寫進 GAP_NOTES。或者明確區分「末列 NaN」與「中間列 NaN」：後者寫進 data_integrity 並 exit 非 0。波動指數（`:339`）同理。

### H7　check_open30：不檢查 session_date 是否為今日

- **位置**：`scripts/check_open30.py:60`（`today = dates[-1]`）、`:137-140`（只看 error 與 bars 是否為空）
- **觸發情境**：美股還沒開盤就執行。2026-11-01 起美國已切回冬令，SKILL 表格的「22:00 後 SPX 開盤確認」其實是紐約 09:00，離開盤還有 30 分鐘。遇到美股假日、或 Yahoo 30m 延遲時也會發生。
- **實際輸出**（stub：假時鐘 2026-11-05 22:00 台北，30m 資料只到 11-04）：
  ```
  exit=0  stdout: OK SPX session_date=2026-11-04 first_30m=UP
  checked_at = "2026-11-05 22:00"，session_date = "2026-11-04"，沒有任何 stale 或 data_status
  ```
  使用者會把前一日的首 30 分方向當作今天的開盤確認。
- **應有行為**：session_date 必須等於「紐約時區的今日」；不等時輸出 `data_status: "NOT_TODAY"`（或 `stale: true`），並 exit 非 0。
- **嚴重度**：高
- **建議修法**：用 `datetime.now(ZoneInfo("America/New_York")).date()` 和 `today` 比對；不等就寫明「今日尚未開盤或資料未更新」並 exit 1。輸出補上 `data_status` 欄位（也見 M4）。

### H8　check_es：時段標籤寫死「台灣牆鐘＋美國夏令」，SOXX 前日資料被當即時

- **位置**：`scripts/check_es.py:52-70`（`now = datetime.now()`，用本機鐘點判時段）、`:163`（`stale = session in ("ASIA_THIN", "EUROPE")`）、`:169-175`（semi 背離）
- **觸發情境**：
  - (a) 冬令（11 月至 3 月）：美股開盤是台北 22:30，但 21:30 起就被標成 `US_REGULAR「美股盤中：即時讀數」`；
  - (b) 任何季節的 `US_PREOPEN`（21:00-21:30 台北）：SOXX 沒有夜盤，fast_info 給的是前一交易日的漲跌，程式卻不標 stale，還拿它和期貨的隔夜漲跌相減，算出「半導體領跌」；
  - (c) 在 GitHub Actions（UTC 時鐘）執行：鐘點完全對不上。
- **實際輸出**：
  ```
  已重現（stub 假時鐘）：
  2026-11-05T14:00Z（台北 22:00＝紐約 09:00，未開盤）→ session=US_REGULAR，soxx 無 note，
      semi_vs_spx={"divergence_pp": -4.68, "read": "半導體領跌(輪動殺半導體)"}
  2026-11-05T13:10Z（台北 21:10＝紐約 08:10）→ session=US_PREOPEN，同上假背離
  已重現（repo 現有資料）：data/es_check.txt 的 checked_at="2026-11-05 01:29"（runner UTC），
      session={"label": "US_REGULAR", "note": "美股盤中：即時讀數"}；
      實際是紐約 11-04 20:29，美股已收盤。
  ```
  `checked_at` 本身也沒有時區，Actions 寫出的 UTC 時間看起來像台北時間。
- **應有行為**：時段應依紐約時區判定，由 zoneinfo 自動處理夏令；SOXX 只有在紐約 09:30-16:00 才算即時，其他時段一律標 stale，也不計算 semi 背離。
- **嚴重度**：高（SKILL 的 21:20「SPX期貨確認」正好落在這個窗口）
- **建議修法**：比照 `cme_session.py`，改用 `datetime.now(ZoneInfo("America/New_York"))` 判斷時段；`checked_at` 改成帶時區的 ISO 字串（或同時寫 UTC 與台北時間）；SOXX 的 stale 條件改為「不在美股正規時段內」。

---

## 3. 中

### M1　check_es：NQ／SOXX 失敗時 except: pass，data_status 仍為 OK

- **位置**：`scripts/check_es.py:151-157`（次期貨）、`:159-177`（SOXX）、`:246-261`（`_err_keys` 只收 `*_error`）
- **觸發情境**：NQ=F（NDX 側是 ES=F）或 SOXX 抓不到。
- **實際輸出**（已重現，stub 拿掉 NQ=F 與 SOXX 報價）：`data_status="OK"`，沒有 `nq_change_pct` 也沒有 `soxx_semis`，`macro_backdrop.note` 仍寫「ES+NQ+10Y+DXY+VIX 合成」，缺項等於 0 分。
- **應有行為**：次期貨是合成分的一項，缺了就應寫 `nq_error`（或 `es_change_pct_error`）並使 data_status 成為 PARTIAL；SOXX 缺失也應留下錯誤欄位。
- **嚴重度**：中
- **建議修法**：兩段 `except` 改成 `result["%s_error" % FUT2_KEY] = str(e)`、`result["soxx_error"] = str(e)`，讓既有的 PARTIAL 邏輯自然接手。

### M2　check_es：隱含開盤整段 except: pass；資料檔缺失或過舊都沒有標記

- **位置**：`scripts/check_es.py:103-148`（外層 `except Exception: pass` 在 `:147-148`）、`:132-138`（pct_fallback）
- **觸發情境**：(a) `today_data.txt` 不存在或損毀；(b) `today_data.txt` 是舊的（例如 H4 的舊快照）。
- **實際輸出**（已重現）：
  ```
  (a) data_status=OK，implied_spx_open 欄位不存在，也沒有 implied_error
  (b) trade_date=2026-10-12、close=6500 → implied_spx_open={"approx": 6458.9, "method": "pct_fallback_degraded", ...}
      data_status=OK，沒有 stale；用「今日 ES 漲跌%」去套「三週前的收盤」
  ```
  `guard.require_symbol` 在檔案不存在時也直接 return（`guard.py:60-61`）。
- **應有行為**：(a) 寫 `implied_open_error: "data file missing/unreadable"`；(b) 比對 trade_date 與預期前一交易日，不符就標 stale 或不輸出 approx。
- **嚴重度**：中
- **建議修法**：外層 except 改為記錄錯誤欄位；est 加上 `index_trade_date`，並與今日（紐約時區）的前一營業日比對。pct_fallback 只在 trade_date 正確時才允許使用。

### M3　check_es：快照退回不檢查年齡，且覆寫原 data_status

- **位置**：`scripts/check_es.py:266-279`（`:272` 直接覆寫 `sd["data_status"]`）
- **觸發情境**：live 全部失敗（ALL_FAILED），而 `data/es_check.txt` 是舊的或本身就是 PARTIAL。
- **實際輸出**（已重現，快照 checked_at=2026-10-01、原 status=PARTIAL）：
  ```
  exit=0  data_status = "SNAPSHOT(from data/, original checked_at=2026-10-01 05:15)"
  macro_backdrop = {"score": 2, "read": "RISK_ON 偏多"}   ← 原本是 PARTIAL 下不可信的合成分
  ```
  原本的 PARTIAL 被抹掉，一個月前的快照也照用、照樣 exit 0。
- **應有行為**：保留原 status（例如 `SNAPSHOT/PARTIAL(...)`）；快照超過一定時數就不採用。
- **嚴重度**：中（SNAPSHOT 字樣仍在，SKILL 規定快速確認時遇 SNAPSHOT 一律回「請在本機執行」，所以有部分緩解）
- **建議修法**：新增 `snapshot_original_status` 欄位；依 `checked_at`（補上時區後）計算年齡，超過門檻就 exit 1。

### M4　check_open30：類股同步與波動指數逐一 except: pass，輸出沒有 data_status

- **位置**：`scripts/check_open30.py:107-118`（sync 迴圈的 `except: pass` 在 `:117`）、`:119-125`、`:127-131`（VIX/VXN）、`:137-140`
- **觸發情境**：^IXIC、SOXX（NDX 側是 SOXX、QQQE）抓不到，或其 30m 資料沒有今日的 K 棒。
- **實際輸出**（已重現，兩個同步標的都拿掉）：`exit=0`，`OK SPX session_date=... first_30m=UP`，沒有 `sector_sync`、沒有 `sync_read`、沒有錯誤欄位。只缺一個時，`sync_read` 會用剩下的那一個判 SYNC 或 DIVERGENT，也沒有標註。
- **應有行為**：rule15 的同步檢查沒做成，必須明示。SKILL（spx-analysis/SKILL.md:542、ndx-analysis/SKILL.md:537）要求「check_open30 必須看 data_status」，但這支腳本根本沒有輸出這個欄位。
- **嚴重度**：中
- **建議修法**：每個失敗的標的寫 `sector_sync_errors`；缺任一個就讓 `sync_read` 加上「[PARTIAL]」；新增 `data_status`（OK／PARTIAL／FAILED），規則比照 check_es。

### M5　check_open30：30m K 未 dropna，NaN 被讀成 FLAT／SYNC

- **位置**：`scripts/check_open30.py:47-51`（`bars_30m` 沒有 dropna）、`:63-72`、`:84`（NaN 比較結果一律 False → FLAT）、`:124-125`（`elif spx_first_dir:` → SYNC）
- **觸發情境**：Yahoo 的 30m K 有 NaN Close，常見於進行中的末根或未結算的首根。
- **實際輸出**（已重現）：
  ```
  首根 Close=NaN → first_30m_direction="FLAT"，sync_read="SYNC：指數與科技/半導體同向，訊號有效"，exit 0
  末根 Close=NaN → current_price=NaN，change_from_open_pct=NaN，exit 0「OK」
  ```
  另外，即使資料正常，只要方向是 FLAT 也會落到「SYNC 訊號有效」，不論類股是漲是跌。
- **應有行為**：NaN 列不得參與判定；首根缺值時 first_30m_direction 應為 null 並 exit 非 0；FLAT 不應被判成「訊號有效」。
- **嚴重度**：中
- **建議修法**：`bars_30m` 回傳前先 `dropna(subset=["Open", "Close"])`；`spx_first_dir == "FLAT"` 另給 `sync_read="N/A：首 30 分無方向"`。

### M6　gap_fix：30m 抓不到時缺日不補、不報

- **位置**：`scripts/gap_fix.py:38-59`（`_intraday_daily_bars` 吞例外回 `{}`）、`:76-77`（`if not intra: return df, notes`）
- **觸發情境**：日線缺一天（2026-08-28 型），同時 30m 端點失敗、被擋或限流。
- **實際輸出**（已重現：`fetch_fixture(gap=True)` 再拿掉 ^GSPC／^VIX 的 30m）：`exit=0`、`data_integrity=null`，stdout 只有通用的 `[yf_compat] default transport failed...`，沒有任何「缺日未能檢查」的訊息。MA／RSI 等全部錯位一天。
- **應有行為**：30m 取不到時，gap 檢查等於沒做，應在 notes 裡回傳「gap_check_unavailable」，讓 fetch_today 寫進 data_integrity（status 例如 `UNVERIFIED`）。
- **嚴重度**：中
- **建議修法**：`patch_missing_days` 在 `intra` 為空時回傳一筆 `{"ticker": t, "status": "gap_check_unavailable"}`；`_intraday_daily_bars` 的 except 要印出例外。另外可加一道不依賴 30m 的檢查：用營業日曆（`pd.bdate_range` 加上美股假日表）比對 daily 序列，找出缺日。

### M7　fetch_today：baseline 損毀時靜默用內建常數

- **位置**：`scripts/fetch_today.py:402-407`（`except Exception: C = DEFAULT_C`；`.get("fetch_today_constants", DEFAULT_C)`）
- **觸發情境**：`docs/regime_baseline.json`（或 NDX 的那份）損毀、被改名，或重算後 key 改名。
- **實際輸出**（已重現）：`exit=0`，`regime.base_5d_pullback=61.65`（內建值；harness 的 baseline 是 60.0），輸出沒有任何「用了 fallback」的欄位。
- **應有行為**：輸出 `regime.constants_source: "baseline" | "DEFAULT_C(fallback)"`，fallback 時印 WARNING。檔案存在但解析失敗時應 exit 非 0（缺檔才允許 fallback）。
- **嚴重度**：中（內建值會隨季度重算越來越舊，卻沒有人會察覺）
- **建議修法**：如上；並把 `except Exception` 收窄為 `FileNotFoundError`。

### M8　參數解析：打錯旗標或缺值一律預設 SPX

- **位置**：`scripts/fetch_today.py:57-66`、`scripts/check_es.py:36-45`、`scripts/check_open30.py:29-38`、`scripts/check_duplicate.py:13-22`（四段相同的手寫解析）
- **觸發情境**：`--symbl ndx`、`--symbol`（沒給值）、`ndx`（位置參數）、`-s ndx` 等。只有 `--symbol=<錯字>` 會被擋下（exit 2）。
- **實際輸出**（已重現）：
  ```
  fetch_today.py --symbl ndx / --symbol / ndx / -s ndx → 全部 exit=0，寫 today_data.txt，"OK symbol=SPX ..."
  check_duplicate.py --symbl ndx → exit=0，symbol: SPX，VERDICT 是 SPX 的
  ```
  使用者以為跑了 NDX，結果 NDX 的檔案仍是舊的，SPX 的檔案則被更新。check_es／check_open30 同理：`ndx_es_check.txt`、`ndx_open30_check.txt` 停留在上次的結果，而這兩個檔沒有 symbol 欄位（L5），也沒有年齡檢查（H7、M3）。
- **應有行為**：遇到任何不認得的參數，或 `--symbol` 沒有值，應 exit 2。
- **嚴重度**：中（guard 的 stamp／require_symbol 會擋住「寫錯檔」，但擋不住「該跑的那一套沒跑」）
- **建議修法**：四支改用 `argparse`，加上 `choices=("spx", "ndx")`，不認得的參數由 argparse 報錯；或在手寫迴圈中對未知參數 exit 2。可以抽成 guard.py 的一個共用函式。

### M9　fetch_today：正常路徑沒有 trade_date 新鮮度檢查

- **位置**：`scripts/fetch_today.py:514-526`（只檢查 trade_date 存在與 NaN）
- **觸發情境**：Yahoo 回傳的序列停在數日前（後端延遲、撤回列），或 runner 的時鐘不對。
- **實際輸出**（已重現）：harness 的 fixture 最後一日是 2026-09-04，在 2026-11-05 執行時，`exit=0`、`OK symbol=SPX trade_date=2026-09-04`，沒有任何警告。SKILL rule37 把「核對 trade_date」交給人工判讀。
- **應有行為**：trade_date 早於「紐約時區最近一個已收盤的交易日」時，至少要在檔內標 `stale_trade_date`；落後 2 個營業日以上應 exit 非 0。
- **嚴重度**：中（H3 修好後，check_duplicate 可以擋住一部分）
- **建議修法**：用 `pd.bdate_range` 加上美股假日表計算預期的 trade_date，比對後寫進 `data_integrity`。

---

## 4. 低

### L1　fetch_today：快照路徑不驗 symbol，也跳過 cross_check

- **位置**：`scripts/fetch_today.py:75-92`；`:532`（`guard.cross_check` 只在正常路徑執行）
- **實際輸出**（已重現）：`data/today_data.txt` 內含 `symbol: "NDX"`、close=21000 時，SPX 的 fetch 會把它拷進 `scripts/today_data.txt`，並 exit 0「OK ... SNAPSHOT」。
- **應有行為**：拷貝前呼叫 `guard.require_symbol(snap, CFG["label"])`，拷貝後跑 `guard.cross_check`。
- **嚴重度**：低（下游 check_duplicate、check_es 的 require_symbol 會以 exit 3 擋下）

### L2　check_duplicate：任何 VERDICT 都 exit 0

- **位置**：`scripts/check_duplicate.py:95`
- **實際輸出**（已重現）：NO_DATA、DUPLICATE 都是 exit 0。
- **應有行為**：OK=0，DUPLICATE、NO_DATA（以及 H2／H3 建議新增的 verdict）用不同的非 0 碼，讓自動流程不必解析文字。
- **嚴重度**：低（SKILL 目前靠讀 VERDICT 判斷）

### L3　fetch_today：breadth 例外或序列不足時回 None，沒有原因

- **位置**：`scripts/fetch_today.py:150-151`（`len(ratio) < 25`）、`:203-204`（`except Exception: return None`）
- **實際輸出**（已重現：SPY 只給 20 列）：`breadth=null`，stdout 完全沒有說明。
- **建議修法**：比照 `_amplitude`，印出 `[breadth] WARNING ...: %r`，並在輸出寫 `breadth_error`。
- **嚴重度**：低（null 至少不會被誤讀成數字）

### L4　NDX 執行時的訊息與標籤寫成 today_data.txt

- **位置**：`scripts/fetch_today.py:302`、`:310`（`"today_data.txt left UNCHANGED"`，`:337`、`:515` 已改用 OUTFILE）；`scripts/check_duplicate.py:63`（`today_data.trade_date`）、`:73`（`MEANING: today_data.txt is empty...`）
- **實際輸出**（已重現）：`check_duplicate.py --symbol ndx` 在 NO_DATA 時印出 `MEANING: today_data.txt is empty/unreadable`。
- **建議修法**：一律改用 `OUTFILE`、`CFG['data']`。
- **嚴重度**：低（誤導排錯方向，但不影響資料）

### L5　check_es／check_open30 的輸出沒有 symbol 欄位

- **位置**：`scripts/check_es.py:263-264`、`scripts/check_open30.py:133-134`（寫檔前沒有 `guard.stamp`）
- **實際輸出**（已重現）：`ndx_es_check.txt` 的 keys 從 `checked_at, session, nq, ...` 開始，沒有 `symbol`；`data/es_check.txt` 也一樣。
- **建議修法**：寫檔前 `guard.stamp(result, CFG["label"])`；讀取端（SKILL、Actions 快照退回）用 `require_symbol` 驗證。
- **嚴重度**：低（目前只能靠檔名，以及 `es`／`nq` 主鍵的差異區分）

### L6　gap_fix：overrides 檔損毀時靜默忽略人工覆寫值

- **位置**：`scripts/gap_fix.py:30-35`
- **實際輸出**（已重現）：`manual_ohlc_overrides.json` 合法時，回補來源是 `30m aggregate (1 bars) + manual override(Close)`；損毀時變成 `30m aggregate (1 bars)`，exit 0，也沒有警告。
- **應有行為**：檔案存在但解析失敗時應印 WARNING，並在 notes 標明「override 檔無法讀取」。
- **嚴重度**：低（source 欄位如實反映沒用到覆寫，但沒人知道是因為讀檔失敗）

### L7　cme_session：不處理 CME 假日與每日維護時段

- **位置**：`scripts/cme_session.py:11-15`（docstring 已聲明「國定假日不處理」）
- **實際輸出**（已重現：直接呼叫）：`weekend_closed(2026-12-25 15:00Z)` 與 `weekend_closed(2027-01-01 15:00Z)` 都回 False。影響是推測的：check_es 在 CME 全日休市日會給一般時段標籤，把前一日結算值當即時讀數。週一至週四 17:00-18:00 ET 的每日維護時段也不在判定內。
- **建議修法**：加入 CME 假日表（每年更新一次），回傳 `HOLIDAY_CLOSED`；維護時段可標 `DAILY_BREAK`。
- **嚴重度**：低（一年只有數天）

---

## 5. 優先順序建議（僅供參考）

1. **H1、H5、H6**：都是「錯的數字＋OK 狀態」，而且修法都是在既有函式裡加檢查，風險小。
2. **H2、H3、L2**：check_duplicate 是三本帳的唯一機械攔截，改成用日期比較，並在讀不到帳本時中止。
3. **H4**：快照退回加檔內標記與年齡門檻，Actions 停用退回。
4. **H7、H8、M4、M5**：盤中與盤前的兩支快速確認腳本，統一用紐約時區，並補上 data_status。
5. 其餘中、低項可以排在後面一起處理。

---

## 附錄 A　重現腳本

放在任何目錄都可以執行（路徑寫死為 `/home/user/spx-analysis`，請依環境調整）。不改 repo 任何檔案；全部在 `tempfile.TemporaryDirectory()` 內執行，不連網。

### A.1　`repro.py`（fetch_today／check_es／check_open30）

用法：`python3 repro.py [f_snap f_vix f_mid f_gap30 f_base f_breadth r_args e_nan e_nq e_nofile e_session e_snap o]`

```python
"""靜默失敗稽核最小重現。全程用 tests/harness.py stub，不連網。"""
import copy, json, sys, os
sys.path.insert(0, "/home/user/spx-analysis/tests")
import harness
import pandas as pd
nan = float("nan")
harness.MODULES = harness.MODULES + ("check_open30.py", "check_duplicate.py")
harness.OUTPUTS = harness.OUTPUTS + ("open30_check.txt", "ndx_open30_check.txt", "dup_check.txt", "ndx_dup_check.txt")

def show(tag, r, keys=None, f=None):
    print("=" * 10, tag, "exit=%s" % r.code)
    print("  stdout:", " | ".join(l for l in r.out.splitlines() if l.strip())[:600])
    if r.err.strip(): print("  stderr tail:", r.err.strip().splitlines()[-1][:300])
    print("  files:", sorted(r.files))
    if f and f in r.files:
        d = json.loads(r.files[f])
        for k in keys or []:
            print("   ", k, "=", json.dumps(d.get(k), ensure_ascii=False)[:300])
    return r

which = sys.argv[1:] or ["all"]
def want(n): return "all" in which or n in which

base = harness.fetch_fixture("spx")
# --- F: fetch_today ----------------------------------------------------------
if want("f_snap"):
    fx = dict(base, mode="raise")
    old = {"trade_date": "2026-10-01", "close": 6500.0, "symbol": "SPX"}
    r = harness.run("fetch_today.py", fx, files={"data/today_data.txt": old, "data/fetched_at.txt": "2026-11-05T01:29:08Z\n"})
    show("F1 snapshot stale (fetch raises, snapshot trade_date=2026-10-01)", r, ["trade_date", "stale", "snapshot", "data_status"], "today_data.txt")
    old_ndx = {"trade_date": "2026-11-04", "close": 21000.0, "symbol": "NDX"}
    r = harness.run("fetch_today.py", fx, files={"data/today_data.txt": old_ndx})
    show("R2 snapshot symbol=NDX copied into SPX file", r, ["symbol", "close"], "today_data.txt")
if want("f_vix"):
    fx = copy.deepcopy(base); df = fx["daily"]["^VIX"]; df["Close"] = nan
    r = harness.run("fetch_today.py", fx)
    show("F2a VIX all-NaN Close -> vix=0", r, ["trade_date", "vix", "regime", "amplitude"], "today_data.txt")
    fx = harness.with_nan(base, "Close", [-1], ticker="^VIX")
    r = harness.run("fetch_today.py", fx)
    d = json.loads(r.files["today_data.txt"]); v = base["daily"]["^VIX"]["Close"]
    show("F2b VIX tail NaN -> yesterday's VIX", r, ["trade_date", "vix"], "today_data.txt")
    print("    VIX[-1]=%.2f VIX[-2]=%.2f ; amplitude.stale=%s" % (v.iloc[-1], v.iloc[-2], (d.get("amplitude") or {}).get("stale")))
if want("f_mid"):
    fx = harness.with_nan(base, "Close", [-2])
    r = harness.run("fetch_today.py", fx)
    d = json.loads(r.files["today_data.txt"]); c = base["daily"]["^GSPC"]["Close"]
    show("F3 index Close NaN at row -2 (prev day)", r, ["trade_date", "prev_close", "change_pct", "data_integrity"], "today_data.txt")
    print("    true prev_close(day-2)=%.2f  day-3=%.2f" % (c.iloc[-2], c.iloc[-3]))
if want("f_gap30"):
    fx = harness.fetch_fixture("spx", gap=True)
    fx["intraday"].pop("^GSPC"); fx["intraday"].pop("^VIX")
    r = harness.run("fetch_today.py", fx)
    show("F4 daily gap + 30m unavailable -> no patch, no flag", r, ["trade_date", "data_integrity", "ma20"], "today_data.txt")
if want("f_base"):
    r = harness.run("fetch_today.py", base, files={"docs/regime_baseline.json": "{corrupt"})
    show("F5 corrupt baseline -> DEFAULT_C silently", r, ["regime"], "today_data.txt")
if want("f_breadth"):
    fx = copy.deepcopy(base); fx["daily"]["SPY"] = fx["daily"]["SPY"].iloc[:20]
    r = harness.run("fetch_today.py", fx)
    show("F6 breadth short series -> None w/o reason", r, ["breadth"], "today_data.txt")
# --- R: routing --------------------------------------------------------------
if want("r_args"):
    fxn = harness.fetch_fixture("ndx")
    fxn["daily"].update(base["daily"]); fxn["intraday"].update(base["intraday"])
    for args in (["--symbl", "ndx"], ["--symbol"], ["ndx"], ["-s", "ndx"]):
        r = harness.run("fetch_today.py", fxn, args)
        print("R1 fetch_today args=%s exit=%s files=%s stdout_last=%s" % (args, r.code, sorted(r.files), r.out.strip().splitlines()[-1]))
# --- E: check_es -------------------------------------------------------------
esf = harness.es_fixture()
if want("e_nan"):
    fx = copy.deepcopy(esf)
    for k in list(fx["quote"]): fx["quote"][k] = (nan, fx["quote"][k][1])
    fx["intraday"] = {}
    r = harness.run("check_es.py", fx, now_utc="2026-11-05T13:00", files=harness.ES_FILES)
    show("E1 all quotes NaN", r, ["data_status", "es", "vix", "us10y", "dxy", "macro_backdrop"], "es_check.txt")
if want("e_nq"):
    fx = copy.deepcopy(esf); fx["quote"].pop("NQ=F"); fx["quote"].pop("SOXX")
    r = harness.run("check_es.py", fx, now_utc="2026-11-05T13:00", files=harness.ES_FILES)
    show("E2 NQ+SOXX missing", r, ["data_status", "nq_change_pct", "soxx_semis", "macro_backdrop"], "es_check.txt")
if want("e_nofile"):
    r = harness.run("check_es.py", esf, now_utc="2026-11-05T13:00")
    show("E3 today_data.txt missing -> implied open silently absent", r, ["data_status", "implied_spx_open"], "es_check.txt")
    old = {"scripts/today_data.txt": {"trade_date": "2026-10-12", "close": 6500.0, "symbol": "SPX"}}
    r = harness.run("check_es.py", esf, now_utc="2026-11-05T13:00", files=old)
    show("E3b today_data.txt stale (2026-10-12)", r, ["data_status", "implied_spx_open"], "es_check.txt")
if want("e_session"):
    for t, what in (("2026-11-05T14:00", "Taipei 22:00 = ET 09:00 pre-open (winter)"),
                    ("2026-11-05T13:10", "Taipei 21:10 = ET 08:10"),
                    ("2026-11-05T06:30", "Taipei 14:30 = ET 01:30")):
        r = harness.run("check_es.py", esf, now_utc=t, files=harness.ES_FILES)
        d = json.loads(r.files["es_check.txt"])
        print("E4 %s (%s): session=%s soxx=%s semi=%s" % (t, what, d["session"]["label"], d.get("soxx_semis"), d.get("semi_vs_spx")))
if want("e_snap"):
    fx = copy.deepcopy(esf); fx["quote"] = {}; fx["intraday"] = {}
    snap = {"checked_at": "2026-10-01 05:15", "session": {"label": "US_PREOPEN"}, "es": {"last": 1, "signal": "BULLISH"},
            "data_status": "PARTIAL(2 core ok, errors: vix_error)", "macro_backdrop": {"score": 2, "read": "RISK_ON 偏多"}}
    r = harness.run("check_es.py", fx, now_utc="2026-11-05T13:00", files=dict(harness.ES_FILES, **{"data/es_check.txt": snap}))
    show("E5 ALL_FAILED -> old PARTIAL snapshot", r, ["checked_at", "data_status", "macro_backdrop"], "es_check.txt")
# --- O: check_open30 ---------------------------------------------------------
def o30_fx(days_back=0, nan_first=False, nan_last=False, drop_sync=()):
    t = pd.date_range("2026-11-02 09:30", periods=13, freq="30min", tz="America/New_York")
    days = [t + pd.Timedelta(days=i) for i in range(4 - days_back)]
    def mk(p0):
        idx = days[0].append(days[1:]) if len(days) > 1 else days[0]
        c = [p0 * (1 + 0.0005 * i) for i in range(len(idx))]
        return pd.DataFrame({"Open": [x * 0.999 for x in c], "High": [x * 1.001 for x in c], "Low": [x * 0.998 for x in c], "Close": c, "Volume": 1000}, index=idx)
    fx = {"daily": {}, "intraday": {"^GSPC": mk(6800), "^IXIC": mk(23000), "SOXX": mk(300)}, "quote": {"^VIX": (18.0, 18.5)}}
    g = fx["intraday"]["^GSPC"]
    if nan_last: g.iloc[-1, g.columns.get_loc("Close")] = nan
    if nan_first:
        first_today = g.index[g.index.date == g.index[-1].date()][0]
        g.loc[first_today, "Close"] = nan
    for s in drop_sync: fx["intraday"].pop(s)
    return fx
if want("o"):
    r = harness.run("check_open30.py", o30_fx(days_back=1), now_utc="2026-11-05T14:00")
    show("O1 run 2026-11-05 22:00 TPE, 30m only up to 11-04", r, ["checked_at", "session_date", "first_30m_direction", "data_status"], "open30_check.txt")
    r = harness.run("check_open30.py", o30_fx(drop_sync=("^IXIC", "SOXX")))
    show("O2 both sync tickers missing", r, ["sector_sync", "sync_read", "data_status"], "open30_check.txt")
    r = harness.run("check_open30.py", o30_fx(nan_first=True, drop_sync=()))
    show("O3 first bar Close NaN", r, ["first_30m_direction", "sync_read", "change_from_open_pct"], "open30_check.txt")
    r = harness.run("check_open30.py", o30_fx(nan_last=True))
    show("O3b last bar Close NaN", r, ["current_price", "change_from_open_pct"], "open30_check.txt")
```

編號對照：F1→H4、R2→L1、F2a/F2b→H5、F3→H6、F4→M6、F5→M7、F6→L3、R1→M8、E1→H1、E2→M1、E3/E3b→M2、E4→H8、E5→M3、O1→H7、O2→M4、O3/O3b→M5。M9 由任一個 fetch case 的 stdout 可見（fixture 末日 2026-09-04，回報 OK）。

### A.2　`repro_dup.py`（check_duplicate，直接在暫存樹執行）

```python
"""check_duplicate 重現：暫存樹直接執行（不需 yfinance stub）。"""
import json, os, shutil, subprocess, sys, tempfile
SRC = "/home/user/spx-analysis/scripts"
def run(files, args=()):
    with tempfile.TemporaryDirectory() as root:
        os.makedirs(os.path.join(root, "scripts")); os.makedirs(os.path.join(root, "docs"))
        for m in ("check_duplicate.py", "guard.py"):
            shutil.copy(os.path.join(SRC, m), os.path.join(root, "scripts", m))
        for rel, c in files.items():
            with open(os.path.join(root, rel), "w", encoding="utf-8") as f:
                f.write(c if isinstance(c, str) else json.dumps(c))
        p = subprocess.run([sys.executable, os.path.join(root, "scripts", "check_duplicate.py"), *args],
                           capture_output=True, encoding="utf-8")
        return p.returncode, p.stdout
td = {"trade_date": "2026-11-04", "close": 6800.0, "symbol": "SPX"}
tdn = {"trade_date": "2026-11-04", "close": 25000.0, "symbol": "NDX"}
la = {"trade_date": "2026-11-05", "data_basis": "2026-11-04 US close"}
ent = {"entries": [{"report_date": "2026-11-05", "grade": "pending"}]}
common = {"scripts/today_data.txt": td, "scripts/ndx_today_data.txt": tdn,
          "docs/track_record.json": ent, "docs/pnl_ledger.json": ent}
def show(tag, r):
    lines = r[1].splitlines()
    print("%-48s exit=%s %s | %s" % (tag, r[0], lines[0] if lines else "", next((l for l in lines if l.startswith("MEANING")), "")))
show("baseline (same close already analysed)", run(dict(common, **{"docs/last_analysis.json": la})))
show("D1 last_analysis.json corrupt", run(dict(common, **{"docs/last_analysis.json": "{corrupt"})))
show("D1 last_analysis.json missing", run(common))
show("D2 trade_date 2026-10-30 < analysed 11-04", run(dict(common, **{"docs/last_analysis.json": la,
     "scripts/today_data.txt": dict(td, trade_date="2026-10-30")})))
show("D3 no data file at all (NO_DATA)", run({"docs/last_analysis.json": la}))
show("R1 --symbl ndx (typo) -> SPX", run(dict(common, **{"docs/last_analysis.json": la}), ["--symbl", "ndx"]))
r = run({"docs/last_analysis.json": la, "scripts/ndx_today_data.txt": "{}"}, ["--symbol", "ndx"])
show("R4 NDX NO_DATA message", r)
# D2b：last_analysis 回滾、帳本已有後續 entry
ent2 = {"entries": [{"report_date": "2026-11-04"}, {"report_date": "2026-11-05", "grade": "pending"}]}
show("D2b ledgers ahead of rolled-back last_analysis", run({"scripts/today_data.txt": td, "scripts/ndx_today_data.txt": tdn,
     "docs/track_record.json": ent2, "docs/pnl_ledger.json": ent2,
     "docs/last_analysis.json": {"trade_date": "2026-11-04", "data_basis": "2026-11-03 US close"}}))
```

編號對照：D1→H2、D2/D2b→H3、D3→L2、R1→M8、R4→L4。

### A.3　其他單點驗證

- **L6**：`harness.fetch_fixture("spx", gap=True)`，並在 `harness.MODULES` 加入 `manual_ohlc_overrides.json`。overrides 合法時，^GSPC 的回補來源含 `+ manual override(Close)`；寫入 `"{corrupt"` 時來源變成純 `30m aggregate`，exit 0。
- **L7**：`cme_session.weekend_closed(datetime(2026,12,25,15,tzinfo=utc))` 與 `datetime(2027,1,1,15,tzinfo=utc)` 皆回 `False`。
- **L5**：`harness.run("check_es.py", harness.es_fixture(), ["--symbol","ndx"], ...)` 的 `ndx_es_check.txt` 沒有 `symbol` key。
- **H8 的現有資料佐證**：`data/es_check.txt` 的 `checked_at="2026-11-05 01:29"`、`session.label="US_REGULAR"`；`data/fetched_at.txt` 為 `2026-11-05T01:29:08Z`。
