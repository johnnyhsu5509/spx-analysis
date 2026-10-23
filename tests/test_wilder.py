import random
import unittest

import pandas as pd

import harness  # 須先 import：把 scripts/ 加入 sys.path
import wilder


def series(values):
    return pd.Series(values, index=pd.bdate_range("2026-01-02", periods=len(values)))


def closes_with(slid_out, today, n=60):
    rnd = random.Random(7)
    rets = [rnd.gauss(0.0005, 0.006) for _ in range(n)]
    rets[-15], rets[-1] = slid_out, today
    c = [5000.0]
    for r in rets:
        c.append(c[-1] * (1 + r))
    return series(c)


class WilderRsiTest(unittest.TestCase):
    def assert_matches_reference(self, closes):
        got = wilder.rsi(series(closes)).tolist()
        ref = harness.ref_wilder(closes)
        self.assertEqual(len(got), len(ref))
        for g, r in zip(got, ref):
            self.assertAlmostEqual(g, r, places=9)

    def test_random_walks_match_reference(self):
        for seed, n in ((1, 15), (2, 40), (3, 330)):
            rnd = random.Random(seed)
            closes = [5000.0]
            for _ in range(n - 1):
                closes.append(closes[-1] * (1 + rnd.gauss(0, 0.01)))
            with self.subTest(seed=seed, n=n):
                self.assert_matches_reference(closes)

    def test_only_gains_is_100(self):
        closes = [100.0 + i for i in range(30)]
        self.assert_matches_reference(closes)
        self.assertEqual(wilder.rsi(series(closes)).iloc[-1], 100.0)

    def test_too_short_is_nan(self):
        self.assertTrue(wilder.rsi(series([100.0 + i for i in range(14)])).isna().all())


class DivergenceTest(unittest.TestCase):
    def test_opposite_moves_flagged(self):
        s = closes_with(slid_out=-0.045, today=-0.006)
        out = wilder.divergence(harness.cutler(s), wilder.rsi(s))
        self.assertTrue(out["flag"])
        self.assertGreater(out["cutler_chg"], 0)
        self.assertLess(out["wilder_chg"], 0)
        self.assertIn("方向相反", out["note"])

    def test_same_direction_not_flagged(self):
        s = closes_with(slid_out=0.001, today=0.012)
        out = wilder.divergence(harness.cutler(s), wilder.rsi(s))
        self.assertFalse(out["flag"])
        self.assertGreater(out["cutler_chg"], 0)
        self.assertGreater(out["wilder_chg"], 0)
        self.assertNotIn("note", out)

    def test_zero_change_is_not_opposite(self):
        out = wilder.divergence(series([50.0, 50.0]), series([55.0, 52.0]))
        self.assertEqual(out, {"flag": False, "cutler_chg": 0.0, "wilder_chg": -3.0})

    def test_missing_is_none_not_neutral(self):
        self.assertIsNone(wilder.divergence(series([float("nan"), 50.0]), series([55.0, 52.0])))
        self.assertIsNone(wilder.divergence(series([48.0, 50.0]), series([55.0, float("nan")])))


if __name__ == "__main__":
    unittest.main()
