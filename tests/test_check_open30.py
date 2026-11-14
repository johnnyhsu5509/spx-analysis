import json
import unittest
from concurrent.futures import ThreadPoolExecutor

import harness  # 須先 import：把 scripts/ 加入 sys.path

OUT = {"spx": "open30_check.txt", "ndx": "ndx_open30_check.txt"}
ARGS = {"spx": (), "ndx": ("--symbol", "ndx")}


class CheckOpen30DateTest(unittest.TestCase):
    """H7：session_date 必須等於紐約今日，否則 data_status=NOT_TODAY 並 exit 非 0。"""

    # (UTC 時刻, 30m 最後一根的紐約日期, 本機時區, 預期 data_status)；註解為 台北／紐約 當地時間
    CASES = [
        ("2026-11-05T14:00", "2026-11-04", None, "NOT_TODAY"),   # 台北 22:00／紐約 09:00 EST 未開盤（稽核 O1）
        ("2026-11-05T14:29", "2026-11-04", None, "NOT_TODAY"),   # 台北 22:29／紐約 09:29 EST 開盤前一分鐘
        ("2026-11-05T15:05", "2026-11-05", None, "OK"),          # 台北 23:05／紐約 10:05 EST
        ("2026-11-06T02:00", "2026-11-05", None, "OK"),          # 台北 11/06 10:00／紐約 11/05 21:00：台北已跨日，紐約仍是 11/05
        ("2026-11-06T02:00", "2026-11-04", None, "NOT_TODAY"),   # 同一時刻但資料只到 11/04（Yahoo 未更新）
        ("2026-10-21T13:00", "2026-10-20", None, "NOT_TODAY"),   # 夏令 台北 21:00／紐約 09:00 EDT 未開盤
        ("2026-10-21T14:05", "2026-10-21", None, "OK"),          # 夏令 台北 22:05／紐約 10:05 EDT
        ("2026-11-07T15:00", "2026-11-06", None, "NOT_TODAY"),   # 紐約週六 10:00：當天沒有交易
        ("2026-11-06T03:00", "2026-11-05", "UTC", "OK"),         # Actions（本機 UTC 11/06 03:00）／紐約 11/05 22:00
        ("2026-11-05T14:00", "2026-11-04", "UTC", "NOT_TODAY"),  # Actions（本機 UTC 11/05 14:00）／紐約 09:00 未開盤
    ]
    NDX = (0, 2, 3, 8)  # 上表中 NDX 也要跑的列

    @classmethod
    def setUpClass(cls):
        jobs = {("spx", i): c for i, c in enumerate(cls.CASES)}
        jobs.update({("ndx", i): cls.CASES[i] for i in cls.NDX})
        fx_fail = harness.open30_fixture("2026-11-05")
        for t in ("^GSPC", "^NDX"):
            fx_fail["intraday"].pop(t)
        cls.fx_fail = fx_fail

        def go(item):
            (sym, _), (ts, last, tz, _) = item
            return harness.run("check_open30.py", harness.open30_fixture(last), ARGS[sym], now_utc=ts, local_tz=tz)

        with ThreadPoolExecutor(max_workers=6) as ex:
            cls.runs = dict(zip(jobs, ex.map(go, jobs.items())))
            cls.fail = dict(zip(("spx", "ndx"), ex.map(
                lambda s: harness.run("check_open30.py", fx_fail, ARGS[s], now_utc="2026-11-05T15:05"), ("spx", "ndx"))))

    def test_status_and_exit_code(self):
        for (sym, i), r in self.runs.items():
            ts, last, tz, want = self.CASES[i]
            with self.subTest(sym=sym, utc=ts, last=last, local_tz=tz):
                d = json.loads(r.files[OUT[sym]])
                self.assertEqual(d["data_status"], want)
                self.assertEqual(d["session_date"], last)
                if want == "OK":
                    self.assertEqual(r.code, 0, r.out + r.err)
                    self.assertTrue(r.out.startswith("OK %s session_date=%s" % (sym.upper(), last)))
                    self.assertEqual(d["ny_today"], last)
                    self.assertNotIn("data_status_note", d)
                    self.assertEqual(d["first_30m_direction"], "UP")
                    self.assertIn("sector_sync", d)
                else:
                    self.assertNotEqual(r.code, 0)
                    self.assertTrue(r.out.startswith("CHECK_OPEN30 NOT_TODAY (%s)" % sym.upper()), r.out)
                    self.assertNotEqual(d["ny_today"], last)
                    self.assertIn("不可當作今日開盤確認", d["data_status_note"])

    def test_ny_date_not_local_date(self):
        """紐約日期與本機日期不同的時刻：以紐約日期為準。"""
        for (sym, i), r in self.runs.items():
            ts, last, tz, want = self.CASES[i]
            if ts in ("2026-11-06T02:00", "2026-11-06T03:00"):
                with self.subTest(sym=sym, utc=ts, last=last):
                    self.assertEqual(json.loads(r.files[OUT[sym]])["ny_today"], "2026-11-05")

    def test_ndx_writes_own_file_only(self):
        for (sym, i), r in self.runs.items():
            if sym == "ndx":
                with self.subTest(utc=self.CASES[i][0]):
                    self.assertEqual(sorted(r.files), ["ndx_open30_check.txt"])

    def test_fetch_failure_status(self):
        for sym, r in self.fail.items():
            with self.subTest(sym=sym):
                self.assertEqual(r.code, 1)
                self.assertIn("CHECK_OPEN30 FAILED (%s)" % sym.upper(), r.out)
                self.assertEqual(json.loads(r.files[OUT[sym]])["data_status"], "FAILED")

    def test_baseline_reproduces_h7(self):
        """原版在稽核 O1 情境回 exit 0、沒有 data_status（證明上面的測試抓得到這個 bug）。"""
        if not harness.has_baseline(harness.ES_BASELINE_REF, "check_open30.py"):
            self.skipTest("找不到基準版本 %s" % harness.ES_BASELINE_REF)
        r = harness.run("check_open30.py", harness.open30_fixture("2026-11-04"), ref=harness.ES_BASELINE_REF,
                        now_utc="2026-11-05T14:00")
        self.assertEqual(r.code, 0)
        d = json.loads(r.files["open30_check.txt"])
        self.assertEqual(d["session_date"], "2026-11-04")
        self.assertNotIn("data_status", d)


if __name__ == "__main__":
    unittest.main()
