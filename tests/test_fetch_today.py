import json
import unittest

import harness

NEW_FIELDS = ["wilder_rsi", "rsi_method_divergence"]


class RegressionTest(unittest.TestCase):
    """固定 fixture 下，原版（BASELINE_REF，預設 origin/main）與新版的舊欄位逐欄相同。"""

    CASES = {
        "spx": ("today_data.txt", (), dict(sym="spx", tail="diverge")),
        "ndx": ("ndx_today_data.txt", ("--symbol", "ndx"), dict(sym="ndx", tail="agree")),
        "spx_gap": ("today_data.txt", (), dict(sym="spx", gap=True)),
    }

    @classmethod
    def setUpClass(cls):
        cls.runs = {}
        if not harness.has_baseline():
            return
        for name, (out, args, kw) in cls.CASES.items():
            fx = harness.fetch_fixture(**kw)
            cls.runs[name] = (out, harness.run("fetch_today.py", fx, args, ref=harness.BASELINE_REF),
                              harness.run("fetch_today.py", fx, args))

    def setUp(self):
        if not self.runs:
            self.skipTest("找不到基準版本 %s" % harness.BASELINE_REF)

    def test_old_fields_identical(self):
        for name, (out, old, new) in self.runs.items():
            with self.subTest(case=name):
                self.assertEqual((old.code, new.code), (0, 0), old.err + new.err)
                self.assertEqual(new.out, old.out)
                self.assertEqual(sorted(new.files), sorted(old.files))
                o, n = json.loads(old.files[out]), json.loads(new.files[out])
                self.assertEqual(list(n)[:len(o)], list(o))
                self.assertEqual(json.dumps({k: n[k] for k in o}, ensure_ascii=False, indent=2), old.files[out])

    def test_cases_exercise_intended_paths(self):
        self.assertEqual(sorted(self.runs["ndx"][2].files), ["ndx_today_data.txt"])
        gap = json.loads(self.runs["spx_gap"][1].files["today_data.txt"])
        self.assertEqual(gap["data_integrity"]["status"], "PATCHED")
        self.assertEqual(gap["breadth"]["tail_source"], "30m_approx")


class NewFieldsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = {"spx": harness.fetch_fixture("spx", tail="diverge"), "ndx": harness.fetch_fixture("ndx", tail="agree")}
        cls.out = {}
        for sym, args, name in (("spx", (), "today_data.txt"), ("ndx", ("--symbol", "ndx"), "ndx_today_data.txt")):
            r = harness.run("fetch_today.py", cls.fx[sym], args)
            assert r.code == 0, r.out + r.err
            cls.out[sym] = json.loads(r.files[name])

    def test_appended_after_existing_fields(self):
        for sym, d in self.out.items():
            with self.subTest(sym=sym):
                self.assertEqual(list(d)[-2:], NEW_FIELDS)

    def test_wilder_matches_reference(self):
        for sym, ticker in (("spx", "^GSPC"), ("ndx", "^NDX")):
            with self.subTest(sym=sym):
                ref = harness.ref_wilder(self.fx[sym]["daily"][ticker]["Close"].tolist())[-1]
                self.assertAlmostEqual(self.out[sym]["wilder_rsi"], ref, delta=0.005 + 1e-9)
                self.assertNotAlmostEqual(self.out[sym]["wilder_rsi"], self.out[sym]["rsi"], delta=0.5)

    def test_divergence_flag(self):
        spx, ndx = self.out["spx"]["rsi_method_divergence"], self.out["ndx"]["rsi_method_divergence"]
        self.assertTrue(spx["flag"])
        self.assertGreater(spx["cutler_chg"], 0)
        self.assertLess(spx["wilder_chg"], 0)
        self.assertIn("note", spx)
        self.assertFalse(ndx["flag"])
        self.assertNotIn("note", ndx)


class FailSafeTest(unittest.TestCase):
    """live 失敗退回 data/ 快照並標 SNAPSHOT；無快照時不寫檔、exit 1。"""

    SENTINEL = '{"trade_date": "2000-01-03", "close": 1.0, "symbol": "SPX"}'

    def test_snapshot_fallback(self):
        for args, name, sym in (((), "today_data.txt", "SPX"), (("--symbol", "ndx"), "ndx_today_data.txt", "NDX")):
            snap = json.dumps({"trade_date": "2026-10-22", "close": 7663.43, "symbol": sym}, indent=2)
            files = {"data/" + name: snap, "data/fetched_at.txt": "2026-10-23T00:00:24Z"}
            if sym == "NDX":
                files["scripts/today_data.txt"] = self.SENTINEL
            with self.subTest(sym=sym):
                r = harness.run("fetch_today.py", {"mode": "raise"}, args, files=files)
                self.assertEqual(r.code, 0, r.out + r.err)
                self.assertIn("SNAPSHOT", r.out)
                self.assertEqual(r.files[name], snap)
                if sym == "NDX":
                    self.assertEqual(r.files["today_data.txt"], self.SENTINEL)

    def test_failures_leave_output_unchanged(self):
        base = harness.fetch_fixture("spx")
        cases = {
            "network": ({"mode": "raise"}, "FETCH FAILED (network/yfinance)"),
            "empty": ({"daily": {}, "intraday": {}}, "FETCH FAILED: empty dataframe"),
            "all_close_nan": (harness.with_nan(base, "Close", slice(None)), "every row has NaN Close"),
            "last_open_nan": (harness.with_nan(base, "Open", slice(-1, None)), "NaN/missing in open"),
        }
        for name, (fx, msg) in cases.items():
            with self.subTest(case=name):
                r = harness.run("fetch_today.py", fx, files={"scripts/today_data.txt": self.SENTINEL})
                self.assertEqual(r.code, 1, r.out + r.err)
                self.assertIn(msg, r.out)
                self.assertEqual(r.files, {"today_data.txt": self.SENTINEL})


if __name__ == "__main__":
    unittest.main()
