"""排程瘦身腳本：用 git 歷史重建 2026-10-20 起每次 SPX／NDX 實跑前後的帳本，逐日比對腳本與實跑。

帳本副本不進 repo（舊帳本有已移除的個人內容）：測試時才用 git show 取出，寫在暫存目錄。不連網、不寫 docs/。
差異只允許出現在下面 KNOWN（數值）與 TEMPLATE（模板字串）列出的欄位，每一條都附原因；每日差異表寫到 stderr。
"""
import ast
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TESTS)
SCRIPTS = os.path.join(REPO, 'scripts')
sys.path.insert(0, SCRIPTS)

import daily_run  # noqa: E402
import ndx_daily_mech  # noqa: E402
import ndx_last_mech  # noqa: E402
import render_ndx_html  # noqa: E402
import render_spx_html  # noqa: E402
import shadow_check as sc  # noqa: E402
import spx_daily_mech  # noqa: E402
from mech_lib import hu, ld, numeric, sv  # noqa: E402

SINCE = '2026-10-20'
EXPECTED = {'spx': ('05bd018', '436057e', 'f45bb65', 'dedb32f', '877fd89', 'bda2806', 'bddd70f', 'df7a3a0', '3512cdd', 'b991687'),
            'ndx': ('dc83855', '7a3c346', '24d3ad9', '8d344a0', '31fea6e', 'ef97c3f', 'c9c0485', 'c59a838', '7094312', '36df61b')}
NEW_SCRIPTS = ('mech_lib.py', 'spx_daily_mech.py', 'ndx_daily_mech.py', 'ndx_last_mech.py', 'render_spx_html.py', 'render_ndx_html.py',
               'daily_run.py', 'shadow_check.py')

REASONS = {
    'R1': '實跑先把 10/19 振幅取 3 位（0.606）才算 log_err；其他天用未取整值。平均值跟著差 0.0002–0.0004',
    'R2': '實跑 backtest_prev 寫 3 位（1.045），同一天 amp_track 寫 4 位（1.0453）',
    'R3': '實跑記帳錯誤：10/28 判定 flat 時漏加 brier.excluded_flat（帳上 flat 已 30 筆、欄位停在 29），之後照抄；腳本從帳本重數＝30',
    'R4': '實跑 actual_pct 在 10/27 以前取 2 位、之後取 3 位；腳本一律 3 位',
    'R5': '10/20 實跑未成交的影子單少寫 fill／stop／exit／exit_type／pnl_pts 五個 null 欄位，之後每天都有寫',
    'T1': '模板措辭：實跑 10/20–10/28 的報告寫「Brier 0.25（Phase 3 恆值）」，10/29 報告的 flat 日措辭也不同；10/30 起與腳本相同',
    'T2': '影子單說明句：實跑每天格式不同（箭頭、附不附高低點與差幾點、停損時間、價格位數）',
    'T3': '振幅帳狀態句：實跑措辭每天不同（區間外・偏低／區間上方／區間下方、附註跳空不計、樣本未達 60 筆）',
    'T4': '半分位取整：實跑同一天 pnl_ledger 停損寫 7771.23、這裡寫 7771.22（自相矛盾）；腳本兩處同一種取整',
    'T5': '漂移基準說明：10/23 以前每項附「A」，11/03 平均寫 -0.55（未補 0）',
    'T6': '價位與百分比位數：實跑時而 28081.2 時而 28081.20、MA200 距離時而 1 位時而 2 位、A 時而 2 位時而 3 位',
    'T7': '10/20 是 rule59 首次每日輸出，實跑在部位水位說明多加一句首日註記',
}
# (系統, 報告日起, 報告日迄, 檔案, 路徑 regex, 原因)；日期 None＝不限
KNOWN = [
    ('spx', '2026-10-20', '2026-10-20', 'track_record.json', r'amp_track\.(entries\[1\]\.(actual_range_pct|log_err|r0_log_err)|summary\.mean_(r0_)?log_err)', 'R1'),
    ('spx', '2026-10-20', '2026-10-20', 'last_analysis.json', r'backtest_prev\.amp\.(actual_range_pct|log_err|r0_log_err)', 'R1'),
    ('spx', '2026-10-21', '2026-10-21', 'last_analysis.json', r'backtest_prev\.amp\.actual_range_pct', 'R2'),
    ('spx', '2026-10-29', None, 'track_record.json', r'summary\.brier\.excluded_flat', 'R3'),
    ('ndx', '2026-10-20', '2026-10-23', 'ndx_track_record.json', r'entries\[\d+\]\.actual_pct', 'R4'),
    ('ndx', '2026-10-20', '2026-10-20', 'ndx_pnl_ledger.json', r'shadow_ledger\.entries\[\d+\]\.(fill|stop|exit|exit_type|pnl_pts)', 'R5'),
]
TEMPLATE = [
    ('spx', 'track_record.json', r'summary\.brier\.note_latest', 'T1'),
    ('spx', 'last_analysis.json', r'backtest_prev\.shadow\.(long|short)', 'T2'),
    ('spx', 'last_analysis.json', r'rule_status\.rule66', 'T3'),
    ('spx', 'last_analysis.json', r'predictions\.shadow_orders\.(long|short)\.stop', 'T4'),
    ('ndx', 'ndx_pnl_ledger.json', r'shadow_ledger\.summary\.drift_bench_note', 'T5'),
    ('ndx', 'ndx_last_analysis.json', r'system_rules_notes\[3\]|backtest_prev\.amp', 'T3'),
    ('ndx', 'ndx_last_analysis.json', r'system_rules_notes\[[24]\]|backtest_prev\.predicted', 'T6'),
    ('ndx', 'ndx_last_analysis.json', r'position_level\.note', 'T7'),
]
HTML_SPX = {'backtest_notes': ['說明'], 'deviation': '偏差', 'amp_note': '振幅說明。', 'macro_title': '盤前', 'macro_note': '宏觀',
            'regime_labels': ['a', 'b', 'c'], 'regime_warn': '環境', 'breadth_note': '廣度', 'price_rows': [['K', 'x', 'up', 'y']],
            'granville': [['買①', 'z']] * 8, 'chan_note': '纏論', 'elliott_rows': [['①', '50%', '', '路徑']], 'bias_note': '偏向',
            'levels': [['1', 'a', '2', 'b']], 'notes_catalyst': 'c&d', 'notes_watch': 'w'}
HTML_NDX = {'title': 'NDX 標題', 'breadth_kpi': 'b', 'vxn_kpi': 'v', 'data_note': 'd', 'deviation': 'dv', 'dims': [['廣度', 'x', 'y']],
            'amp_warn': 'aw', 'regime_labels': ['a', 'b', 'c'], 'ndx_band': 'n', 'spx_band': 's', 'cross_label': 'l', 'cross_note': 'cn',
            'news': 'nw', 'news_sources': 'src'}


def history_ok():
    try:
        for sym, shas in EXPECTED.items():
            for s in shas:
                if subprocess.run(['git', '-C', REPO, 'cat-file', '-e', f'{s}^:docs/{sc.SYM[sym]["last"]}'],
                                  capture_output=True, encoding='utf-8').returncode:
                    return False
    except OSError:
        return False
    return True


def classify(sym, rep, d):
    f, kind, path, a, b = d
    if numeric(d[1:]) or kind != 'value':
        hit = [r for s, lo, hi, ff, rx, r in KNOWN if s == sym and ff == f and (lo is None or rep >= lo) and (hi is None or rep <= hi) and re.fullmatch(rx, path)]
        return ('數值' if numeric(d[1:]) else '欄位有無'), (hit[0] if hit else None)
    hit = [r for s, ff, rx, r in TEMPLATE if s == sym and ff == f and re.fullmatch(rx, path)]
    return '字串', (hit[0] if hit else None)


def snapshot(d):
    out = {}
    for f in os.listdir(d):
        with open(os.path.join(d, f), 'rb') as fh:
            out[f] = fh.read()
    return out


class LedgerReplayTest(unittest.TestCase):
    """逐日重算 2026-10-20 起每次實跑，與實跑 commit 的帳本逐欄比對。"""

    @classmethod
    def setUpClass(cls):
        cls.results = {}
        if not history_ok():
            return
        for sym in EXPECTED:
            cls.results[sym] = sc.replay_all(sym, sc.analysis_commits(sym, SINCE))

    @classmethod
    def tearDownClass(cls):
        if not cls.results:
            return
        out = ['', '| 系統 | 報告日 | 判定日 | commit | 輸入修正 | 數值 | 字串 | 欄位有無 | 差異（原因代號） |', '|---|---|---|---|---|---|---|---|---|']
        detail = []
        for sym, rs in cls.results.items():
            for r in rs:
                cnt = {'數值': 0, '字串': 0, '欄位有無': 0}
                why = {}
                for d in r['diffs']:
                    kind, reason = classify(sym, r['report_date'], d)
                    cnt[kind] += 1
                    why[reason or '未說明'] = why.get(reason or '未說明', 0) + 1
                    detail.append(f"{sym} {r['report_date']} {d[0]}:{d[2]}［{reason}］{sc.side(d[1], d[3], d[4])}")
                out.append(f"| {sym.upper()} | {r['report_date']} | {r['eval_date']} | {r['sha'][:7]} | {len(r['inputs_fixed'])} | {cnt['數值']} | {cnt['字串']} | "
                           f"{cnt['欄位有無']} | {'、'.join(f'{k}×{v}' for k, v in why.items()) or '—'} |")
        out += ['', '原因代號：'] + [f'- {k}：{v}' for k, v in REASONS.items()] + ['', '逐條差異：'] + [f'- {x}' for x in detail]
        sys.stderr.write('\n'.join(out) + '\n')

    def setUp(self):
        if not self.results:
            self.skipTest('git 歷史不足（shallow clone 或缺 commit），無法重建 fixtures')

    def test_found_every_analysis_commit(self):
        for sym, shas in EXPECTED.items():
            got = [r['sha'][:7] for r in self.results[sym]]
            self.assertEqual(got[:len(shas)], list(shas), sym)

    def test_every_difference_is_explained(self):
        for sym, rs in self.results.items():
            for r in rs:
                for d in r['diffs']:
                    with self.subTest(sym=sym, report=r['report_date'], path=f'{d[0]}:{d[2]}'):
                        self.assertIsNotNone(classify(sym, r['report_date'], d)[1], '未說明的差異：' + sc.side(d[1], d[3], d[4]))

    def test_known_numeric_differences_still_occur(self):
        """KNOWN 每一條都要真的出現過，避免清單過寬。"""
        for s, lo, hi, f, rx, reason in KNOWN:
            seen = [d for r in self.results[s] for d in r['diffs'] if d[0] == f and re.fullmatch(rx, d[2])
                    and (lo is None or r['report_date'] >= lo) and (hi is None or r['report_date'] <= hi)]
            self.assertTrue(seen, f'{s} {f} {rx}（{reason}）沒有出現')

    def test_pnl_ledgers_identical_except_known(self):
        for sym, f in (('spx', 'pnl_ledger.json'), ('ndx', 'ndx_pnl_ledger.json')):
            for r in self.results[sym]:
                left = [d for d in r['diffs'] if d[0] == f and classify(sym, r['report_date'], d)[1] not in ('R5', 'T5')]
                self.assertEqual(left, [], f"{sym} {r['report_date']}")

    def test_gap_day_reproduced(self):
        spx = [r for r in self.results['spx'] if r['report_date'] == '2026-10-27'][0]
        ndx = [r for r in self.results['ndx'] if r['report_date'] == '2026-10-27'][0]
        for r, files in ((spx, ('track_record.json', 'pnl_ledger.json')), (ndx, ('ndx_track_record.json', 'ndx_pnl_ledger.json'))):
            self.assertEqual((r['eval_date'], r['trade_date']), ('2026-10-23', '2026-10-26'))
            self.assertEqual([d for d in r['diffs'] if d[0] in files and numeric(d[1:])], [])
        self.assertEqual(spx['mech']['track_record.json']['summary']['gap_days'][-1], '2026-10-26')
        self.assertEqual(ndx['mech']['ndx_track_record.json']['amp_track']['summary']['gap_days'], ['2026-10-26'])


@unittest.skipUnless(history_ok(), 'git 歷史不足（shallow clone 或缺 commit），無法重建 fixtures')
class GuardAndCliTest(unittest.TestCase):
    """防呆與 CLI：沒有 --out 不寫帳本、該擋的情況要擋。用 10/22 的實跑當 fixture。"""

    @classmethod
    def setUpClass(cls):
        cls.spx = sc.replay_all('spx', [sc.git('rev-parse', 'f45bb65').strip()])[0]
        cls.ndx = sc.replay_all('ndx', [sc.git('rev-parse', '24d3ad9').strip()])[0]

    def docs(self, root, r, sym):
        d = os.path.join(root, 'docs')
        os.makedirs(d)
        for f in sc.SYM[sym]['files']:
            sv(os.path.join(d, f), sc.show(f"{r['sha']}^", f'docs/{f}'))
        if sym == 'ndx':
            sv(os.path.join(d, 'last_analysis.json'), sc.show(f"{r['sha']}^", 'docs/last_analysis.json'))
        return d

    def cli(self, *args):
        return subprocess.run([sys.executable, *args], capture_output=True, encoding='utf-8')

    def test_no_out_writes_no_ledger(self):
        with tempfile.TemporaryDirectory() as root:
            d = self.docs(root, self.spx, 'spx')
            before = snapshot(d)
            sv(os.path.join(root, 'td.json'), self.spx['today'])
            sv(os.path.join(root, 'nar.json'), self.spx['narrative'])
            rpt = os.path.join(root, 'rpt.txt')
            p = self.cli(os.path.join(SCRIPTS, 'spx_daily_mech.py'), '--docs', d, '--today', os.path.join(root, 'td.json'),
                         '--narrative', os.path.join(root, 'nar.json'), '--report', rpt)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(snapshot(d), before)
            self.assertEqual(sorted(os.listdir(root)), ['docs', 'nar.json', 'rpt.txt', 'td.json'])
            self.assertIsNone(ld(rpt)['wrote'])
            out = os.path.join(root, 'out')
            p = self.cli(os.path.join(SCRIPTS, 'spx_daily_mech.py'), '--docs', d, '--today', os.path.join(root, 'td.json'),
                         '--narrative', os.path.join(root, 'nar.json'), '--report', rpt, '--out', out, '--report-date', '2026-10-22')
            self.assertEqual(p.returncode, 0, p.stderr)
            for f in spx_daily_mech.FILES:
                with open(os.path.join(out, f), encoding='utf-8') as fh:
                    self.assertEqual(fh.read(), json.dumps(self.spx['mech'][f], ensure_ascii=False, indent=1))

    def test_daily_run_without_out_writes_only_report(self):
        with tempfile.TemporaryDirectory() as root:
            d = self.docs(root, self.ndx, 'ndx')
            sv(os.path.join(root, 'td.json'), self.ndx['today'])
            sv(os.path.join(root, 'aux.json'), sc.ndx_aux(self.ndx['after']))
            sv(os.path.join(root, 'nar.json'), {**self.ndx['narrative'], 'html': HTML_NDX})
            with open(os.path.join(d, 'ndx-analysis-20261021.html'), 'w', encoding='utf-8') as f:
                f.write(sc.git('show', f"{self.ndx['sha']}^:docs/ndx-analysis-20261021.html"))
            args = ['--symbol', 'ndx', '--docs', d, '--today', os.path.join(root, 'td.json'), '--aux', os.path.join(root, 'aux.json'),
                    '--narrative', os.path.join(root, 'nar.json'), '--report', os.path.join(root, 'rpt.txt')]
            daily_run.main(args)
            self.assertEqual(sorted(os.listdir(root)), ['aux.json', 'docs', 'nar.json', 'rpt.txt', 'td.json'])
            out = os.path.join(root, 'out')
            rep = daily_run.main(args + ['--out', out])
            self.assertEqual(sorted(os.listdir(out)), ['ndx', 'ndx-analysis-20261022.html', 'ndx_last_analysis.json', 'ndx_pnl_ledger.json', 'ndx_track_record.json'])
            self.assertEqual(os.listdir(os.path.join(out, 'ndx')), ['index.html'])
            self.assertEqual(rep['spx_last'], os.path.join(d, 'last_analysis.json'))
            for f in sc.SYM['ndx']['files']:
                self.assertEqual(ld(os.path.join(out, f)), self.ndx['mech'][f])

    def assert_stops(self, msg, fn):
        with self.assertRaises(SystemExit) as cm:
            fn()
        self.assertIn(msg, str(cm.exception))

    def test_spx_guards(self):
        with tempfile.TemporaryDirectory() as root:
            d = self.docs(root, self.spx, 'spx')
            td = self.spx['today']
            for f, o in self.spx['after'].items():
                sv(os.path.join(root, f), o)
            self.assert_stops('DUPLICATE', lambda: spx_daily_mech.build(root, td))
            self.assert_stops('amplitude 缺或過期', lambda: spx_daily_mech.build(d, {**td, 'amplitude': {**td['amplitude'], 'stale': True}}))
            for f, edit, msg in (('pnl_ledger.json', lambda o: o['entries'][-1]['trades_pending'].append({'side': 'long'}), '有實單'),
                                 ('track_record.json', lambda o: o['entries'][-1].update(pullback_prob=60), '偏離 50')):
                o = ld(os.path.join(d, f))
                edit(o)
                with tempfile.TemporaryDirectory() as d2:
                    for g in spx_daily_mech.FILES:
                        sv(os.path.join(d2, g), o if g == f else ld(os.path.join(d, g)))
                    self.assert_stops(msg, lambda: spx_daily_mech.build(d2, td))

    def test_ndx_guards(self):
        with tempfile.TemporaryDirectory() as root:
            d = self.docs(root, self.ndx, 'ndx')
            td, aux = self.ndx['today'], sc.ndx_aux(self.ndx['after'])
            ledgers, _ = ndx_daily_mech.build(d, td)
            spx = ld(os.path.join(d, 'last_analysis.json'))
            self.assert_stops('SPX 今天還沒跑完', lambda: ndx_last_mech.build(d, ledgers, td, aux, {**spx, 'data_basis': '2026-10-20 US close'}))
            self.assert_stops('部位水位切換', lambda: ndx_last_mech.build(d, ledgers, {**td, 'ma200': td['close'] + 1}, aux, spx))
            self.assert_stops('先跑 ndx_daily_mech', lambda: ndx_last_mech.build(d, {f: ld(os.path.join(d, f)) for f in ndx_daily_mech.FILES}, td, aux, spx))

    def test_shadow_check_cli(self):
        with tempfile.TemporaryDirectory() as root:
            for sha, code in (('f45bb65', 0), ('bddd70f', 1)):
                rpt = os.path.join(root, f'{sha}.md')
                p = self.cli(os.path.join(SCRIPTS, 'shadow_check.py'), '--symbol', 'spx', sha, '--report', rpt)
                self.assertEqual(p.returncode, code, p.stderr)
                with open(rpt, encoding='utf-8') as f:
                    self.assertIn(f'數值差異 {code}', f.read())


@unittest.skipUnless(history_ok(), 'git 歷史不足（shallow clone 或缺 commit），無法重建 fixtures')
class HtmlRenderTest(unittest.TestCase):
    """每天的實跑帳本都要能渲染，且報告裡的數字跟帳本一致（敘事用佔位字）。"""

    def test_render_every_day(self):
        for sym, render, H in (('spx', render_spx_html.render, HTML_SPX), ('ndx', render_ndx_html.render, HTML_NDX)):
            for r in sc.replay_all(sym, sc.analysis_commits(sym, SINCE)):
                with self.subTest(sym=sym, report=r['report_date']):
                    a = r['after']
                    last = a[sc.SYM[sym]['last']]
                    head = glob.glob(os.path.join(REPO, 'docs', f"{sym}-analysis-{r['report_date'].replace('-', '')}.html"))[0]
                    page = render(a, r['today'], {'html': H}, render_spx_html.head_from(head, last['trade_date']))
                    self.assertIn(f"<title>{'SPX' if sym == 'spx' else 'NDX'} 日線分析 {last['trade_date']}</title>", page)
                    pend = (a['pnl_ledger.json'] if sym == 'spx' else a['ndx_pnl_ledger.json'])['shadow_ledger']['pending']
                    for x in pend:
                        self.assertIn(f"{x['limit']:,.2f}", page)
                    self.assertIn(f"{hu(last['amplitude']['A_pct'], 2):.2f}%", page)
                    self.assertNotIn('None', page)

    def test_missing_required_field_stops(self):
        r = sc.replay_all('spx', [sc.git('rev-parse', 'f45bb65').strip()])[0]
        head = os.path.join(REPO, 'docs', 'spx-analysis-20261022.html')
        with self.assertRaises(SystemExit) as cm:
            render_spx_html.render(r['after'], r['today'], {'html': {k: v for k, v in HTML_SPX.items() if k != 'deviation'}}, render_spx_html.head_from(head, '2026-10-22'))
        self.assertIn('deviation', str(cm.exception))


class EncodingTest(unittest.TestCase):
    """這些腳本也在 Windows（預設 cp950）跑：open() 與 subprocess 一律明寫 encoding='utf-8'。"""

    def test_open_and_subprocess_specify_utf8(self):
        for name in NEW_SCRIPTS:
            with open(os.path.join(SCRIPTS, name), encoding='utf-8') as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                f = getattr(node, 'func', None)
                if isinstance(f, ast.Name) and f.id == 'open' or isinstance(f, ast.Attribute) and f.attr == 'run' and getattr(f.value, 'id', '') == 'subprocess':
                    with self.subTest(script=name, line=node.lineno):
                        self.assertEqual([k.value.value for k in node.keywords if k.arg == 'encoding'], ['utf-8'])


if __name__ == '__main__':
    unittest.main()
