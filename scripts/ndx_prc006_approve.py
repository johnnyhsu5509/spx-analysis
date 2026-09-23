import json

D = "../docs/"


def load(n):
    return json.load(open(D + n, encoding="utf-8"))


def save(n, o):
    json.dump(o, open(D + n, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


p = load("ndx_pnl_ledger.json")
prc = [x for x in p["proposed_rule_changes"] if x["id"] == "prc-006"][0]
p["proposed_rule_changes"] = [x for x in p["proposed_rule_changes"] if x["id"] != "prc-006"]
prc.update({
    "status": "APPROVED — 2026-09-23 已套用至 sim_rules.intraday_sequencing，自 2026-09-23 策略表起生效",
    "approved_on": "2026-09-23",
    "approved_by": "Johnny",
    "approval_context": "NDX session 2026-09-23 直接核准。",
    "effective_from": "trades_pending report_date 2026-09-23（尚未評估，依 rule40 可套用）",
    "retroactive_policy": "依 rule40，已結算的 8/28、9/18 不重判；summary.cumulative_if_intraday_checked 保留作為揭露口徑。",
    "handover_note": "僅套用於 NDX 帳本。SPX 帳本是否採用同一規則未處理，須由 SPX session 另行提請 Johnny 決定。",
})
p["approved_rule_changes"].append(prc)
p["sim_rules"]["intraday_sequencing"] = (
    "【2026-09-23 核准・prc-006】限價單（limit_buy／limit_sell／buy_stop）成交當日，若目標或停損亦在日線範圍內，"
    "改以 30 分 K 判定：只計入成交那根 K 棒之後的價格行為；同一根 K 棒內無法判序時，保守視為未觸及目標（停損仍計入）。"
    "30 分 K 無法取得時退回日線規則並標註。sell_stop_close_confirm 以收盤成交、當日不判出場，不受影響。")
p["trades_pending"]["eval_rule"] = "用 2026-09-23 美股 NDX OHLC 判定；適用 rule50（prc-004）與 **prc-006（30 分 K 判定成交與目標／停損先後）**。"
save("ndx_pnl_ledger.json", p)

a = load("ndx_last_analysis.json")
a["system_rules"].append("rule51 限價單同日成交＋觸價改以 30 分 K 判序（prc-006，2026-09-23 核准）")
a["predictions"]["watch_points"] = [w for w in a["predictions"]["watch_points"] if "prc-006" not in w]
a["system_rules_notes"].append("prc-006 於 2026-09-23 核准，自本日策略表起生效（rule51）")
save("ndx_last_analysis.json", a)

for f in ["ndx-analysis-20260923.html", "ndx/index.html"]:
    h = open(D + f, encoding="utf-8").read()
    old = h[h.index("<h2>七、待 Johnny 決定</h2>"):h.index("<footer>")]
    new = ('<h2>七、規則更新</h2>\n<div class="box good">\n  <b>prc-006 已核准（2026-09-23）</b>：限價單成交當天，若目標或停損也在日線範圍內，'
           '改用 30 分 K 判斷先後，只計成交之後的價格行為。自本日策略表起生效；8/28、9/18 已結算不重判（rule40）。\n</div>\n\n')
    open(D + f, "w", encoding="utf-8").write(h.replace(old, new))
open("_prc006.txt", "w").write("ok")
