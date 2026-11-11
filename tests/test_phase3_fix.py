"""Phase 3 修正（2026-11-04）：部位水位 position_level、振幅命中率、頂端摘要行與 phase3_fields.py。不連網、不寫 docs。"""
import copy
import json
import os
import sys
import tempfile
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TESTS)
sys.path.insert(0, os.path.join(REPO, 'scripts'))

import mech_lib as ml  # noqa: E402
import phase3_fields as pf  # noqa: E402

def rb(path, enc=None):
    """讀檔後立刻關閉（enc 為 None 讀 bytes）。"""
    with open(path, 'rb') if enc is None else open(path, encoding=enc) as fh:
        return fh.read()


ENT = [{'eval_date': '2026-10-16', 'band_lo': 1.0, 'band_hi': 2.0, 'actual_range_pct': 1.0},     # 下緣端點＝命中
       {'eval_date': '2026-10-19', 'band_lo': 1.0, 'band_hi': 2.0, 'actual_range_pct': 2.0},     # 上緣端點＝命中
       {'eval_date': '2026-10-20', 'band_lo': 1.0, 'band_hi': 2.0, 'actual_range_pct': 0.99},    # 低於
       {'eval_date': '2026-10-21', 'band_lo': 1.0, 'band_hi': 2.0, 'actual_range_pct': 2.01},    # 高於
       {'eval_date': '2026-10-22', 'band_lo': 1.0, 'band_hi': 2.0, 'actual_range_pct': 1.5, 'in_band': False}]  # 旗標說謊也要重判


def la_fixture():
    return {'trade_date': '2026-11-04', 'data_basis': '2026-11-03 US close', 'close': 7568.92, 'direction': {'prob': 50, 'bias': '中性', 'rule': None},
            'pullback_prob': 50, 'amplitude': {'A_pct': 1.015, 'A_pts': 76.82, 'band_lo': 0.73, 'band_hi': 1.282},
            'predictions': {'key_support': [7545, 7528, 7508], 'key_resistance': [7580, 7595]}}


def tr_fixture(events=True):
    tr = {'amp_track': {'entries': copy.deepcopy(ENT)}}
    if events:
        tr['position_gate'] = {'events': [{'date': '2026-04-08', 'from': '半倉', 'to': '正常'}]}
    return tr


class PositionLevelTest(unittest.TestCase):
    OLD = {'state': '正常', 'since': '2026-04-08'}

    def test_same_rule_as_ndx_ma200(self):
        p = ml.position_level(self.OLD, 7568.92, 7315.89, '2026-11-03')
        self.assertEqual((p['state'], p['pct'], p['dist_to_switch_pct'], p['since']), ('正常', 3.46, 3.34, '2026-04-08'))
        self.assertEqual(sorted(p), sorted(['state', 'close', 'ma200', 'pct', 'since', 'switched_today', 'data_missing', 'basis_date', 'dist_to_switch_pct', 'note']))
        self.assertFalse(p['switched_today'])

    def test_equal_close_is_half_position(self):
        with self.assertRaises(SystemExit) as cm:
            ml.position_level(None, 100.0, 100.0, 'd')
        self.assertIn('半倉', str(cm.exception))

    def test_switch_stops_for_manual_handling(self):
        with self.assertRaises(SystemExit) as cm:
            ml.position_level(self.OLD, 7300.0, 7315.89, 'd')
        self.assertIn('部位水位切換', str(cm.exception))

    def test_bootstrap_without_old_has_no_since(self):
        self.assertIsNone(ml.position_level(None, 110.0, 100.0, 'd')['since'])

    def test_seed_from_gate_events(self):
        self.assertEqual(ml.seed_position(tr_fixture()), {'state': '正常', 'since': '2026-04-08'})
        self.assertIsNone(ml.seed_position(tr_fixture(False)))


class AmpHitRateTest(unittest.TestCase):
    def test_edges_inclusive_and_flag_ignored(self):
        h = ml.amp_hit_rate(ENT)
        self.assertEqual((h['n'], h['hits'], h['below_band'], h['above_band']), (5, 3, 1, 1))
        self.assertEqual((h['date_from'], h['date_to'], h['rate_pct']), ('2026-10-16', '2026-10-22', 60.0))
        self.assertIn('未達 60 筆', h['note'])

    def test_empty(self):
        h = ml.amp_hit_rate([])
        self.assertEqual((h['n'], h['hits'], h['rate_pct'], h['date_from']), (0, 0, None, None))

    def test_pending_entries_ignored(self):
        self.assertEqual(ml.amp_hit_rate(ENT + [{'eval_date': 'x', 'band_lo': 1, 'band_hi': 2, 'actual_range_pct': None}])['n'], 5)

    def test_real_ledgers_agree_with_their_own_summary(self):
        """帳本逐筆重判的命中數，必須等於 amp_track.summary 記的覆蓋率與每筆 in_band 旗標。"""
        for f in ('track_record.json', 'ndx_track_record.json'):
            with open(os.path.join(REPO, 'docs', f), encoding='utf-8') as fh:
                at = json.load(fh)['amp_track']
            h = ml.amp_hit_rate(at['entries'])
            self.assertEqual(h['hits'], sum(bool(e['in_band']) for e in at['entries']), f)
            self.assertEqual(h['rate_pct'], at['summary']['band_coverage_pct'], f)


class SummaryLineTest(unittest.TestCase):
    def line(self, ev):
        la = la_fixture()
        if ev is not False:
            la['event_day'] = ev
        pos = ml.position_level(PositionLevelTest.OLD, 7568.92, 7315.89, '2026-11-03')
        return ml.summary_line('SPX', la, pos)

    def test_has_all_required_parts(self):
        s = self.line({'is_event_day': True, 'note': '期中選舉'})
        for part in ('資料日 2026-11-03', '方向 50', 'A 1.02%', '±77 點', '0.73–1.28%', 'MA200 7,315.89', '+3.46%', '水位正常',
                     '支撐 7,545／7,528', '壓力 7,580／7,595', '預報日 2026-11-04', '事件日：是（期中選舉）'):
            self.assertIn(part, s)

    def test_event_day_not_guessed(self):
        self.assertTrue(self.line(False).endswith('事件日：未標註'))
        self.assertTrue(self.line({'is_event_day': None, 'note': ''}).endswith('事件日：未標註'))
        self.assertTrue(self.line({'is_event_day': False, 'note': ''}).endswith('事件日：否'))

    def test_missing_levels_show_dash(self):
        la = la_fixture()
        la['predictions'] = {}
        pos = ml.position_level(PositionLevelTest.OLD, 7568.92, 7315.89, '2026-11-03')
        self.assertIn('支撐 — 壓力 —', ml.summary_line('SPX', la, pos))


class HtmlInjectTest(unittest.TestCase):
    PAGE = '<html><head></head><body>\n<div class="wrap">\n<header>H</header>\n<footer>F</footer>\n</div>\n</body></html>\n'

    def la(self):
        la = la_fixture()
        la['amp_hit_rate'] = ml.amp_hit_rate(ENT)
        la['summary_line'] = 'SPX｜測試 & 摘要'
        la['position_level'] = ml.position_level(PositionLevelTest.OLD, 7568.92, 7315.89, '2026-11-03')
        return la

    def test_banner_goes_first_and_escapes(self):
        out = ml.inject_banner(self.PAGE, self.la())
        self.assertLess(out.index('phase3-summary'), out.index('<header>'))
        self.assertGreater(out.index('phase3-summary'), out.index('<div class="wrap">'))
        self.assertIn('SPX｜測試 &amp; 摘要', out)
        self.assertIn('3/5 ＝ 60.0%', out)

    def test_idempotent(self):
        la = self.la()
        once = ml.inject_banner(self.PAGE, la)
        self.assertEqual(ml.inject_banner(once, la), once)
        twice = ml.inject_position(once, ml.position_html('SPX', la['position_level']))
        self.assertEqual(ml.inject_position(twice, ml.position_html('SPX', la['position_level'])), twice)
        self.assertLess(twice.index('部位水位（部位層，不是分析）'), twice.index('<footer>'))

    def test_summary_replaced_not_duplicated(self):
        la = self.la()
        once = ml.inject_banner(self.PAGE, la)
        la['summary_line'] = 'SPX｜第二版'
        out = ml.inject_banner(once, la)
        self.assertEqual(out.count('phase3-summary'), 1)
        self.assertIn('第二版', out)
        self.assertNotIn('測試', out)


class Phase3FieldsCliTest(unittest.TestCase):
    TD = {'trade_date': '2026-11-03', 'close': 7568.92, 'ma200': 7315.89}

    NDX_GATE = {'state': '正常', 'close': 25979.36, 'ma200': 24822.71, 'pct': 4.66, 'since': '2026-04-08', 'switched_today': False,
                'data_missing': False, 'basis_date': '2026-11-03', 'dist_to_switch_pct': 4.45, 'note': ''}

    def docs(self, root, events=True, position=None, ndx_gate=NDX_GATE):
        d = os.path.join(root, 'docs')
        os.makedirs(d)
        la = la_fixture()
        if position:
            la['position_level'] = position
        files = [('last_analysis.json', la), ('track_record.json', tr_fixture(events))]
        if ndx_gate:
            files.append(('ndx_last_analysis.json', {'position_level': ndx_gate}))
        for f, o in files:
            with open(os.path.join(d, f), 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(json.dumps(o, ensure_ascii=False, indent=1))
        return d, la

    def test_build_adds_fields_and_keeps_direction(self):
        with tempfile.TemporaryDirectory() as root:
            d, orig = self.docs(root)
            la = pf.build('spx', d, self.TD, True, '期中選舉')
            self.assertEqual(la['position_level']['since'], '2026-04-08')
            self.assertEqual((la['direction'], la['pullback_prob']), (orig['direction'], 50))
            self.assertEqual(la['amp_hit_rate']['hits'], 3)
            self.assertIn('事件日：是（期中選舉）', la['summary_line'])

    def test_stops_without_start_date(self):
        with tempfile.TemporaryDirectory() as root:
            d, _ = self.docs(root, events=False)
            with self.assertRaises(SystemExit) as cm:
                pf.build('spx', d, self.TD)
            self.assertIn('position_gate', str(cm.exception))

    def test_stops_when_dates_do_not_match(self):
        with tempfile.TemporaryDirectory() as root:
            d, _ = self.docs(root)
            with self.assertRaises(SystemExit):
                pf.build('spx', d, {**self.TD, 'trade_date': '2026-11-02'})

    def test_stops_on_direction_not_50(self):
        with tempfile.TemporaryDirectory() as root:
            d, la = self.docs(root)
            la['direction']['prob'] = 60
            with open(os.path.join(d, 'last_analysis.json'), 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(json.dumps(la, ensure_ascii=False))
            with self.assertRaises(SystemExit):
                pf.build('spx', d, self.TD)

    def test_cli_without_apply_writes_nothing_and_apply_is_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            d, _ = self.docs(root)
            td, page, rpt = (os.path.join(root, x) for x in ('td.json', 'p.html', 'r.json'))
            for p, c in ((td, json.dumps(self.TD)), (page, HtmlInjectTest.PAGE)):
                with open(p, 'w', encoding='utf-8', newline='') as fh:
                    fh.write(c)
            before = {f: rb(os.path.join(d, f)) for f in os.listdir(d)}
            args = ['--symbol', 'spx', '--docs', d, '--today', td, '--html', page, '--report', rpt]
            pf.main(args)
            self.assertEqual({f: rb(os.path.join(d, f)) for f in os.listdir(d)}, before)
            self.assertEqual(rb(page, 'utf-8'), HtmlInjectTest.PAGE)
            pf.main(args + ['--apply'])
            h1 = rb(page)
            j1 = rb(os.path.join(d, 'last_analysis.json'))
            pf.main(args + ['--apply'])
            self.assertEqual((rb(page), rb(os.path.join(d, 'last_analysis.json'))), (h1, j1))
            self.assertIn('phase3-summary'.encode(), h1)
            self.assertIn('部位水位'.encode(), h1)

    def test_spx_uses_ndx_gate_and_notes_stale_data(self):
        with tempfile.TemporaryDirectory() as root:
            d, _ = self.docs(root)
            ha = pf.build('spx', d, self.TD, ndx_td_files=())['holding_action']
            self.assertEqual((ha['action'], ha['target_pct']), ('維持', 100))
            self.assertIn('NDX 收盤 25,979.36', ha['text'])
            self.assertNotIn('⚠', ha['text'])
        with tempfile.TemporaryDirectory() as root:
            d, _ = self.docs(root, ndx_gate={**self.NDX_GATE, 'basis_date': '2026-10-31'})
            ha = pf.build('spx', d, self.TD, ndx_td_files=())['holding_action']
            self.assertIn('NDX 閘門資料日為 2026-10-31', ha['text'])
            self.assertEqual(ha['action'], '維持')

    def test_spx_stops_without_ndx_gate(self):
        with tempfile.TemporaryDirectory() as root:
            d, _ = self.docs(root, ndx_gate=None)
            with self.assertRaises(SystemExit) as cm:
                pf.build('spx', d, self.TD, ndx_td_files=())
            self.assertIn('NDX 閘門', str(cm.exception))

    def test_half_position_does_not_stop_and_records_switch_once(self):
        with tempfile.TemporaryDirectory() as root:
            d, _ = self.docs(root)
            td, rpt = os.path.join(root, 'td.json'), os.path.join(root, 'r.json')
            with open(td, 'w', encoding='utf-8') as fh:
                fh.write(json.dumps({**self.TD, 'ma200': 7600.0}))
            args = ['--symbol', 'spx', '--docs', d, '--today', td, '--report', rpt, '--ndx-today', '--apply']
            la = pf.main(args)
            self.assertEqual((la['position_level']['state'], la['position_level']['switched_today']), ('半倉', True))
            self.assertEqual(la['direction']['prob'], 50)
            pf.main(args)
            with open(os.path.join(d, 'track_record.json'), encoding='utf-8') as fh:
                ev = json.load(fh)['position_gate']['events']
            self.assertEqual([(e['date'], e['to']) for e in ev], [('2026-04-08', '正常'), ('2026-11-03', '半倉')])


class HoldingActionTest(unittest.TestCase):
    """方案 G：第一句只有 維持／加碼／減碼；分母是這一籃；出清只能出現在「另案討論」註記；判定式與 position_level 相同。"""
    MA = 27976.53

    def gate(self, old_state, close):
        return ml.position_state({'state': old_state, 'since': '2026-04-08'}, close, self.MA, '2026-11-05')

    def test_four_states(self):
        for old, close, act, tgt, sw in (('正常', 29000.0, '維持', 100, False), ('半倉', 29000.0, '加碼', 100, True),
                                         ('正常', 26629.81, '減碼', 50, True), ('半倉', 26629.81, '維持', 50, False)):
            with self.subTest(old=old, close=close):
                g = self.gate(old, close)
                self.assertEqual(g['switched_today'], sw)
                self.assertEqual(g['state'], '正常' if close > self.MA else '半倉')
                ha = ml.holding_action(g, '2026-11-06')
                self.assertEqual((ha['action'], ha['target_pct']), (act, tgt))
                self.assertTrue(ha['text'].startswith(f'對現有{ml.BASKET}（以這一籃為 100%，不是帳戶總曝險）：{act}'))

    def test_same_rule_as_position_level(self):
        old = {'state': '正常', 'since': '2026-04-08'}
        a, b = ml.position_state(old, 7568.92, 7315.89, '2026-11-03'), ml.position_level(old, 7568.92, 7315.89, '2026-11-03')
        self.assertEqual({k: a[k] for k in b}, b)
        self.assertEqual(ml.position_state(None, 100.0, 100.0, 'd')['state'], '半倉')

    def test_forbidden_words_and_exit_only_as_side_note(self):
        for old, close in (('正常', 29000.0), ('半倉', 29000.0), ('正常', 26629.81), ('半倉', 26629.81)):
            text = ml.holding_action(self.gate(old, close), '2026-11-06')['text']
            with self.subTest(old=old, close=close):
                for w in ('觀望', '防守', '不交易'):
                    self.assertNotIn(w, text)
                self.assertEqual(text.count('出清'), text.count(ml.EXIT_ALL))

    def test_half_reclaim_distance(self):
        g = self.gate('半倉', 26629.81)
        self.assertEqual(g['rise_to_reclaim_pct'], 5.06)
        self.assertIn('收盤需再漲 5.1% 站回 MA200 才加回 100%', ml.holding_action(g, '2026-11-06')['text'])
        self.assertIn('收盤需再漲 5.1% 站回 MA200 才恢復正常', ml.position_html('SPX', g))

    def test_banner_puts_action_before_summary(self):
        la = HtmlInjectTest().la()
        la['holding_action'] = ml.holding_action(self.gate('正常', 26629.81), '2026-11-06')
        la['holding_action']['semis_ref'] = ml.semis_ref(None)
        out = ml.inject_banner(HtmlInjectTest.PAGE, la)
        self.assertLess(out.index('減碼到 50%'), out.index('新增多單'))
        self.assertLess(out.index('新增多單'), out.index('SPX｜測試'))
        self.assertIn('不得以 0 代入', out)

    def test_semis_for_borrows_same_day_only(self):
        sd = {'as_of': '2026-11-09', 'basis': '^SOX', 'change_pct': 6.85, 'vs_index_pp': 3.45, 'read': '半導體領漲（領先指數 ≥1.0pp）'}
        ndx = {'symbol': 'NDX', 'trade_date': '2026-11-09', 'semis_daily': sd}
        spx = {'symbol': 'SPX', 'trade_date': '2026-11-09', 'change_pct': 2.35}
        got = ml.semis_for(spx, [ndx])
        self.assertEqual((got['change_pct'], got['vs_index_pp'], got['borrowed_from']), (6.85, 4.5, 'NDX'))
        self.assertIn('取自 NDX 同日資料', ml.semis_ref(got))
        self.assertIs(ml.semis_for({**spx, 'semis_daily': {**sd, 'basis': 'SOXX'}}, [ndx])['basis'], 'SOXX')
        self.assertIsNone(ml.semis_for(spx, [{**ndx, 'semis_daily': {**sd, 'as_of': '2026-11-06'}}]))
        self.assertIsNone(ml.semis_for(spx, [{**ndx, 'semis_daily': None}]))
        self.assertIn('資料缺（不得以 0 代入）', ml.semis_ref(ml.semis_for(spx, [])))
        self.assertNotIn('+0.00%', ml.semis_ref(None))

    def test_spx_level_wording_cannot_be_read_as_basket(self):
        pos = ml.position_state({'state': '正常', 'since': '2026-04-08'}, 7568.92, 7315.89, '2026-11-03')
        la = la_fixture()
        s = ml.summary_line('SPX', la, pos)
        self.assertIn('SPX 自身水位正常；科技籃倉位跟 NDX', s)
        self.assertIn('・水位正常', ml.summary_line('NDX', la, pos))
        h = ml.position_html('SPX', pos)
        self.assertIn('SPX 自身水位：<b>正常</b>', h)
        self.assertIn('這一籃的倉位一律跟 NDX 閘門', h)

    def test_semis_ref(self):
        sd = {'as_of': '2026-11-05', 'basis': '^SOX', 'change_pct': -3.21, 'vs_index_pp': -1.5, 'read': '半導體領跌（落後指數 ≥1.0pp）',
              'chg_5d_pct': None, 'vs_ma200_pct': 2.0, 'tail_source': '30m_approx'}
        s = ml.semis_ref(sd)
        for part in ('^SOX', '資料日 2026-11-05', '日 -3.21%', '-1.50pp', '5 日 —', '近似值', '不改水位'):
            self.assertIn(part, s)


if __name__ == '__main__':
    unittest.main()
