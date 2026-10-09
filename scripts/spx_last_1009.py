import json
F = "../docs/last_analysis.json"
L = json.load(open(F, encoding="utf-8"))
R = ("中性（**今日無 edge，不掛**）。10/8 S&P 跳空 -0.30% 開 7,778.45、13:00 ET 低 7,731.26（跌破 10/7 低 7,763），收 7,765.36（-0.47%），收在 7,763 之上 2 點。"
 "主因 AI／晶片股殺盤（ChatGPT 營收低於預期報導、NDX -1.39%、晶片指數 -3.35%）＋Brent 103.8（+3.6%，伊朗戰事、荷莫茲油輪遇襲）。"
 "偏多：收回 7,763、10Y 反落至 5.231%、**廣度反轉擴張**（RSP/SPY +1.05% 近似、Russell 持平、Dow +0.1%）、VIX 15.41、均線多頭排列。"
 "偏空：**MACD 柱四日來首度縮小**（12.21→10.18）、收在 MA5 之下、連兩日收黑、百元油價、距 MA200 +7.17%。"
 "headline **52%**（rule16：跌 33＋整理 38×0.5）；**rule62 三條全中（bias 中性、46–54、離散度 4pp）→ 全日不掛（連 5 日）**。"
 "定調：**這次跌的是權值與晶片，等權和小型股反而撐住——是輪動不是撤退；但動能第一次轉弱，7,731 是新的分界。**")
L.update({
 "trade_date": "2026-10-09", "data_basis": "2026-10-08 US close", "close": 7765.36, "change_pct": -0.47, "vix": 15.41,
 "pullback_prob": 52, "rating": R,
 "news_check": {
  "as_of": "2026-10-09 上午 台北（rule52）",
  "10/8 行情歸因": "**AI 交易受挫＋油價急漲**：S&P -0.5% 收 7,765.36（ATH 後連兩日收低）、Nasdaq -1.3%、Dow +0.1%；科技股領跌，報導指 ChatGPT 開發商年化營收將低於部分預估，晶片指數 -3.4%（AP／Yahoo Finance／Bloomberg）",
  "油價／伊朗": "Brent 盤中破 104（Python 收 103.8，+3.6%），為 9/29 以來首度；驅動：美伊戰事未見協議、荷莫茲附近油輪遇襲、墨西哥灣熱帶風暴減產。Trump 發言報導互相矛盾（一說不要協議、一說期中選舉前不攻擊伊朗）→ **待查證，不計入評分**；rule2 續適用",
  "殖利率": "^TNX 5.231（-4.6bps）。報導稱 10Y 早盤上衝後午後回落、10/7 盤中曾達 5.36%（2002 年來高）——與 ^TNX 數值有落差，**以 Python ^TNX 為準**",
  "Fed": "9 月紀要偏向年底前再升息；下次決議 10/28",
  "本週": "10/13 JPMorgan 開啟財報季；10/9 開盤前未查到 rule23 清單內重大數據（21:20 複核）",
  "症狀vs病因": "晶片股重挫是 AI 營收預期下修（病因在 AI 資本支出回報疑慮），油價急漲是伊朗供給風險（病因在戰事）；10Y 反落說明這天不是利率驅動。**等權撐住、權值下跌＝資金從 AI 權值輪出，非全面去風險**",
  "查證": "收盤以 Python 為準（與報導 7,765.36 一致）。一則 AP 摘要稱 Russell 2000 -1.4%，與 Python ^RUT（2,793.20→2,794.13，持平）不符，研判為 10/7 數字，以 Python 為準；Fortune 稱 Brent 108.33 為離群值，不採用"},
 "macro_layer": {"es_pct": -0.25, "es_pt_chg_since_spx_close": 5.75, "nq_pct": -1.16, "us10y_pct": 5.231, "us10y_note": "-4.6bps（DOWN_RISK_ON）",
  "dxy": 102.11, "vix": 15.41, "soxx_prev_pct": -3.35, "backdrop_score": 1, "session_label": "ASIA_THIN", "implied_spx_open": 7771.1,
  "backdrop": "**盤前合成 +1（MIXED），亞洲薄盤、不可執行**。ES -0.25%、NQ -1.16% 皆相對前一結算（含 10/8 盤中殺盤）；**自 SPX 收盤後 ES +5.75 點**，隱含開盤約 7,771（+0.07%）。10Y 5.231（-4.6bps）、DXY 102.11（-0.12%）、VIX 15.41、SOXX 前日 -3.35%。21:00 後須複查"},
 "sector_rotation": {"theme": "**AI 權值與晶片領跌，等權與小型股撐住**",
  "note": "S&P -0.47%、NDX -1.39%、SOXX -3.35%，但 Dow +0.1%、Russell 持平、RSP/SPY 1 日 +1.05%（近似）＝殺在 AI 權值。前 3 日是『權值撐、小型殺』，今天反過來；依 rule29 單日輪動不外推，依 rule41 晶片跌幅不直接推導指數（NDX/SPX 傳導約 0.34）",
  "position_note": "上方：7,782（wave-1 頂）、7,798（10/8 高）、**7,807（10/7 高）**、7,845（ATH 盤中高）。下方：**7,763（10/7 低）**、**7,731（10/8 低）**、7,700（中樞上沿）、7,667（中樞下沿）。（依 rule19／rule32，個人部位建議不寫入本檔）"},
 "breadth": {"rsp_spy_ratio": 0.2738, "chg_1d_pct": 1.05, "chg_5d_pct": 0.1, "vs_ma20_pct": -0.66, "as_of": "2026-10-08", "tail_source": "30m_approx",
  "divergence": "【rule51】as_of＝trade_date，末筆由 30m 補值（近似值）。**1 日 +1.05% 反轉擴張、5 日 +0.10% 回到中性**，結束連 3 日窄化；指數跌而廣度升＝輪動。依 rule29 同步指標、不主導方向"},
 "regime_check": {"subjective": 52, "subjective_unit": "隔日收盤下跌機率", "objective_avg": 55.4, "objective_unit": "未來5日盤中低點跌破-0.75%的機率", "vs_base": -6.2,
  "alignment": "【rule30】主觀 52%（中性）vs 客觀 -6.2pp（VIX<16 -12.2、趨勢 -4.7、MA20 -1.8，三維同向偏多）→ 分歧；依 rule62 本就不掛。**【rule55】regime 連 5 日未變 → 本期無解析度**。單位不同，禁比絕對值"},
 "six_factors": {"overheat_25": 50, "ma_deviation_20": 68, "rate_fx_event_30": 78, "volume_exhaustion_15": 50, "wave_chan_10": 50, "weighted": 62.0,
  "note": "六因子 62.0 不進 headline（rule16），與 52 差 10.0pp。過熱項 50：BB 73.7%、Wilder RSI 56.2、KD 71.4/67.4，已降溫。乖離項 68：距 MA200 +7.17%。事件項 78：rule2 下限 75，Brent 103.8、AI 營收疑慮；10Y 回落抵銷部分。量能項 50：rule40 初值 3.52B。波浪項 50：MACD 柱首度縮小、盤中破 10/7 低但收回"},
 "predictions": {
  "short_bias": "中性 52%，今日無 edge（rule62）。偏多：收回 7,763、10Y 反落、廣度反轉擴張、VIX <16、均線多頭排列。偏空：MACD 柱首度縮小、收在 MA5 下、連兩黑、NDX -1.39%／晶片 -3.35%、Brent 103.8。情景：A 收跌 ≤-0.3%（≤7,742）33%；B 平盤 38%；C 收漲 ≥+0.3%（≥7,789）29%。headline＝52%。**rule62 三條全中 → 全日不掛**",
  "key_resistance": [7782, 7807, 7845], "key_support": [7763, 7731, 7700, 7667],
  "fib_targets": {"ma5": 7776.55, "ma5_next_rule44": 7795.2, "ma20": 7697.05, "ma20_next": 7702.2, "ma50": 7689.44, "ma50_next": 7697.1, "ma200": 7245.96,
   "zhongshu_upper": 7699.6, "zhongshu_lower": 7666.6, "bb_upper": 7841.47, "bb_lower": 7552.63,
   "high20": 7844.52, "ath_high": 7844.52, "ath_close": 7818.93, "day_low_1007": 7763.34, "day_low_1008": 7731.26, "day_high_1008": 7797.79, "wave1_high": 7782.19, "wave2_low": 7616.78, "w3_equal_w1": 7891.2, "fib382_w2_to_ath": 7757.5, "fib500_w2_to_ath": 7730.7},
  "zhongshu": {"upper": 7699.6, "lower": 7666.6, "note": "向上筆 7,616.78→7,844.52 後回落；10/8 低 7,731.26 恰在該筆 50% 回撤（7,730.7），未進中樞；MACD 柱首度縮小。收破 7,731＝向上筆結束、回測中樞上沿 7,700；收回 7,807＝回踩完成"},
  "elliott": "①**wave-3 內小 4 浪**（45%）：7,731–7,845 區間整理，10/8 低恰在 50% 回撤 ②**wave-3 延伸重啟**（30%）：收過 7,807 → 7,845 → 7,891 ③**假突破**（25%）：收破 7,731（50% 回撤）→ 7,700 中樞上沿 → 7,667。**分界：上 7,807、下 7,731**",
  "strategies": {},
  "rule27_rejected": [
   {"name": "short_resist", "order": "limit_sell", "entry": 7795, "stop": 7830, "t1": 7745, "rr": 1.43, "dist_pct": 0.38, "reason": "rule62；RR 1.43 須減半"},
   {"name": "short_breakdown", "order": "sell_stop_close_confirm", "entry": "收破 7,731", "stop": 7770, "t1": 7700, "dist_pct": -0.44, "reason": "rule62"},
   {"name": "long_pullback", "order": "limit_buy", "entry": 7735, "stop": 7695, "t1": 7790, "rr": 1.38, "dist_pct": -0.39, "reason": "rule62；超出 rule31 下行門檻、RR 1.38 須減半"},
   {"name": "breakout_long", "order": "buy_stop", "entry": 7808, "dist_pct": 0.55, "reason": "rule27 超標；rule3 MACD 柱縮小＋量能初值不成立；rule62"}],
  "watch_points": [
   "**7,731（10/8 低＝50% 回撤）**：收破＝向上筆結束、情景③，下看 7,700",
   "**7,807（10/7 高）**：收盤站上＝小 4 浪結束、wave-3 重啟往 7,845",
   "**7,763（10/7 低）**：已兩日盤中跌破，收盤若再失守＝支撐轉弱",
   "**MACD 柱**：10.18 首度縮小，若連縮且價格再創高＝頂背馳",
   "**晶片／AI 權值**：SOXX -3.35%；止跌與否決定 NDX 是否續拖指數",
   "**廣度**：RSP/SPY 1 日 +1.05%（近似），若續擴張＝輪動、非撤退",
   "**Brent 103.8**：站穩 104 以上＝通膨溢價升溫",
   "**10Y 5.231%**：回 5.30% 以上＝利率壓力重啟",
   "**10/13 JPMorgan 財報季開跑**；10/28 FOMC",
   "**rule62 連五日不掛**：對照組 10/5、10/6 空單、10/7、10/8 多單皆被掃停損"]},
 "catalysts": ["AI 營收疑慮：晶片指數 -3.4%、NDX -1.39%", "Brent 103.8（+3.6%）：伊朗戰事、荷莫茲油輪遇襲、墨西哥灣減產",
  "S&P -0.47% 收 7,765.36，盤中低 7,731 後收回；Dow +0.1%、Russell 持平", "10Y 回落至 5.231%", "10/13 JPMorgan 開啟財報季；10/28 FOMC"],
 "event_week": {"active": False, "event_score": 5.5, "label": "財報季前、油價升溫", "events": ["伊朗（rule2）", "Brent 104", "AI 營收疑慮", "10/13 財報季開跑"],
  "two_horizon": {"next_day": "中性 52%、無 edge：**不掛**（rule62）",
   "5d": "**收過 7,807** → 7,845 → wave-3 延伸；**收破 7,731** → 7,700 中樞上沿 → 7,667"},
  "posture": "**跌的是 AI 權值，撐的是等權。**晶片殺 3%、油破 104，S&P 只收 -0.47% 而且收回 10/7 低之上；但 MACD 柱第一次縮小，動能在退。兩邊都有理，明天沒有方向優勢——**不掛是正確結果。**"},
 "backtest_prev": {"graded_date": "2026-10-08", "predicted": "47% 中性", "actual": "收 7,765.36（-0.47%，down），開 7,778.45／低 7,731.26／高 7,797.79",
  "grade": "half（中性遇跌）", "brier": 0.2809, "rolling_direction_pct": 62.9, "always_neutral_baseline_pct": 68.6, "mean_brier": 0.2477, "pnl_day_bp": 0.0, "pnl_cum_bp": -1.88,
  "summary": "**中性遇跌＝half**，情景 A（27%）兌現；Brier 0.2809 輸給 0.25。AI／晶片殺盤＋Brent 104，盤中破 10/7 低 7,763、收盤守住。**rule62 對照：long_pullback 7,775 首根成交、被 13:00 低 7,731.3 掃停損 -35 點**——連四日擋掉停損單。依 rule17 並列：系統 62.9% vs 每天報中性 68.6%；Brier 0.2477 vs 0.25"},
 "dashboard_url": "https://johnnyhsu5509.github.io/spx-analysis/spx/",
 "analysis_purity_note": "依 rule32，本次分析未摻入任何個人財務條件"})
rc = L["rule_candidates"]
rc["rule56"] += "｜**10/8 非本型態**（開 7,778.45、高 7,797.79 在 12:00），樣本維持 4"
rc["macro_asia_thin"] += "｜**10/8：亞盤推算 7,798.5、實際開 7,778.45（差 20 點，低估跳空）**——計為錯，**已5（4 錯 1 對）→ 已達結案數，待 Johnny 核准轉正或改寫**（排程執行不自行轉正）"
L["rule_status"] = {"as_of": "2026-10-09", "basis": "2026-10-08 US close",
 "rule1": "不觸發：MACD 柱 +10.18",
 "rule2": "續觸發：伊朗戰事、荷莫茲油輪遇襲、Brent 103.8 → 事件因子下限 75（實給 78）",
 "rule3": "阻擋突破多：MACD 柱縮小、量能為初值 3.52B",
 "rule4": "列入催化劑：10/13 財報季開跑；10/9 無重大數據",
 "rule5": "不適用：BB 73.7%",
 "rule9": "不觸發：event_score 5.5",
 "rule12": "不適用（無破位單）",
 "rule14": "不觸發：BB 73.7%、Wilder RSI 56.2",
 "rule16": "跌 33 ＋ 整理 38×0.5 ＝ 52；六因子 62.0（差 10.0pp）",
 "rule17": "系統 62.9% vs 每天報中性 68.6%；Brier 0.2477 vs 0.25",
 "rule20": "適用：均線多頭排列且收盤在 MA20 之上 → 偏空上限 60%（未觸頂）",
 "rule23": "不適用：10/9 開盤前未查到清單內重大數據（21:20 複核）",
 "rule27": "門檻 0.469%，可執行 7,729–7,802",
 "rule29": "廣度 1 日反轉擴張，同步指標，不主導",
 "rule30": "主觀中性 vs regime 偏多（三維同向）→ 分歧；本日不掛",
 "rule31": "上行 0.557%（≤7,809）／下行 0.139%（≥7,755），回踩單超出",
 "rule32": "未摻個人財務條件",
 "rule40": "10/8 量 3.52B 為初值 → 中性 50",
 "rule41": "NDX -1.39% vs SPX -0.47%（傳導約 0.34）；SOXX -3.35% 不直接推導指數",
 "rule43": "不觸發：近 4 日 +0.66／+0.58／-0.22／-0.47，非正負相間",
 "rule44": "MA5 近 3 日 +29.6／+30.0／+19.8 同號 → 7,795；MA20 +7.3／+8.3／+8.7 → 7,702；MA50 → 7,697",
 "rule51": "as_of＝trade_date，但 tail_source 30m_approx → 廣度為近似值",
 "rule52": "第二十次執行：查明 AI 營收疑慮殺晶片、Brent 破 104（伊朗／油輪遇襲／墨西哥灣減產）；Trump 發言矛盾列待查證；排除 Russell -1.4% 與 Brent 108 兩則不符資料",
 "rule55": "**觸發：regime 連 5 日未變 → 本期無解析度**",
 "rule57": "10/9 無掛單",
 "rule61": "參考單停損皆 ≥0.5×ATR（33.7 點）且放結構位外",
 "rule62": "**觸發全日不掛**：bias 中性＋headline 52（46–54）＋離散度 4pp（<10），三條全中（連 5 日）",
 "rule56": "10/8 不符，樣本維持 4",
 "data_integrity": "10Y 以 ^TNX 5.231 為準（報導 5.32% 有落差）；KD 採 9 日算法（71.4/67.4），today_data 的 75.5/75.3 為不同算法；RSI 採 Wilder 56.2（today_data 60.9 為 Cutler）；10/8 成交量 3.52B 為初值；SOXX 取 check_es 10/8 收（aux 為 10/7）；Russell 以 Python 為準"}
json.dump(L, open(F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open("spx_last_1009.txt", "w", encoding="utf-8").write("ok " + str(len(L["rule_candidates"])))
