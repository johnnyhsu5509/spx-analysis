import json

D = "../docs/"
RULE = ("rule54 多頭排列時過熱因子不計偏空：MA5>MA20>MA50>MA200 成立時，RSI>70、%B>100、距 MA200>10% "
        "不得作為上調跌情景（C）的理由，視為中性；非多頭排列時照舊（prc-009，2026-10-13 核准）")

p = json.load(open(D + "ndx_pnl_ledger.json", encoding="utf-8"))
assert not any(x["id"] == "prc-009" for x in p["approved_rule_changes"])
p["approved_rule_changes"].append({
    "id": "prc-009", "raised_on": "2026-10-07", "approved_on": "2026-10-13", "approved_by": "Johnny",
    "status": "APPROVED — 2026-10-13 寫入 system_rules rule54，自 2026-10-14 報告起生效",
    "issue": "主觀評分把多頭趨勢中的過熱訊號（RSI>70、%B>100、距 MA200>10%）算成偏空，headline 長期被推回 50 上方；上線以來從未報出『偏多』。",
    "evidence": "scripts/backtest_trend_exception.py（NDX 2010–2026，4,215 日）：四線多頭時過熱日的 5 日拉回率 51.2%，低於基準 56.5% 與非多頭的 60–61%；%B>100 僅 43.3%、次日跌比率 17.1%（基準 27.7%）。2010–2018 與 2019–2026 兩子期方向一致。",
    "fix_applied": "四線多頭排列成立時，三項過熱因子在情景權重調整中不得上調 C；六因子參考分數的『過熱度』『乖離率』同步以中性 50 計。非多頭排列時維持原規則。",
    "scope_limit": "只改評分校準，不改 rule16 推導式、不改 rule52／rule53、不改策略單型。方案 A（趨勢例外／追突破）經同一回測否決，未採用。",
    "retroactive_policy": "依 rule40 只前瞻套用；2026-10-13 報告已產出，不重算。",
    "expected_effect": "多頭排列期間 headline 約下移 3–5pp。**不會讓系統變成常報強方向**：同一回測顯示各情境下『次日跌% + 0.5×平盤%』都落在 44–47，次日方向本身幾乎不可預測。",
    "spx_note": "僅套用 NDX；SPX 未測，不可直接套用。"})
json.dump(p, open(D + "ndx_pnl_ledger.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

a = json.load(open(D + "ndx_last_analysis.json", encoding="utf-8"))
a["system_rules"].append(RULE)
json.dump(a, open(D + "ndx_last_analysis.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

OLD1 = "| 技術指標過熱度 | 25% | RSI>70/布林上軌/KD高檔 |"
NEW1 = "| 技術指標過熱度 | 25% | RSI>70/布林上軌/KD高檔（**rule54：四線多頭排列時以中性計**）|"
ANCHOR = "**額外硬規則（NDX 專屬）**：不得因為"
ADD = ("**【硬規則・rule54】多頭排列時過熱因子不計偏空（prc-009，2026-10-13 Johnny 核准，自 10/14 報告起）：**\n"
       "- 條件：MA5 > MA20 > MA50 > MA200（四線多頭排列）\n"
       "- 成立時，**RSI>70、布林 %B>100、距 MA200>10% 不得作為上調跌情景（C）的理由**，一律視為中性；六因子參考的「過熱度」「乖離率」同步以 50 計\n"
       "- 非多頭排列時照原規則計\n"
       "- 依據：`scripts/backtest_trend_exception.py`（2010–2026，4,215 日）——多頭中過熱日的 5 日拉回率 51.2%（基準 56.5%），%B>100 僅 43.3%。同回測否決了「趨勢例外／追突破」（buy_stop −0.10 ATR/筆、t=−4.3），**不得以本規則為由新增追價單**\n\n")
for f in ("../skills/ndx-analysis/SKILL.md", "C:/Users/User/.claude/skills/ndx-analysis/SKILL.md"):
    s = open(f, encoding="utf-8", newline="").read()
    assert OLD1 in s and ANCHOR in s and "rule54】多頭排列" not in s, f
    nl = "\r\n" if "\r\n" in s else "\n"
    s = s.replace(OLD1, NEW1).replace(ANCHOR, ADD.replace("\n", nl) + ANCHOR)
    open(f, "w", encoding="utf-8", newline="").write(s)
open("_prc009.txt", "w").write("ok")
