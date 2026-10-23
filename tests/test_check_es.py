import json
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import harness  # 須先 import：把 scripts/ 加入 sys.path
import cme_session

NOTE = "此為前一交易日結算值，非即時"


def utc(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


class WeekendClosedTest(unittest.TestCase):
    # (UTC 時刻, 預期)；註解為紐約當地時間
    BOUNDARIES = [
        ("2026-10-23T20:59", False),  # 週五 16:59 EDT
        ("2026-10-23T21:00", True),   # 週五 17:00 EDT
        ("2026-10-25T21:59", True),   # 週日 17:59 EDT
        ("2026-10-25T22:00", False),  # 週日 18:00 EDT
        # 2026-03-08（週日）凌晨進入夏令：週五仍是 EST(UTC-5)、週日已是 EDT(UTC-4)
        ("2026-03-06T21:59", False),  # 週五 16:59 EST
        ("2026-03-06T22:00", True),   # 週五 17:00 EST
        ("2026-03-08T21:59", True),   # 週日 17:59 EDT
        ("2026-03-08T22:00", False),  # 週日 18:00 EDT
        # 2026-11-01（週日）凌晨結束夏令：週五仍是 EDT(UTC-4)、週日已是 EST(UTC-5)
        ("2026-10-30T20:59", False),  # 週五 16:59 EDT
        ("2026-10-30T21:00", True),   # 週五 17:00 EDT
        ("2026-11-01T22:59", True),   # 週日 17:59 EST
        ("2026-11-01T23:00", False),  # 週日 18:00 EST
    ]

    def test_boundaries(self):
        for ts, want in self.BOUNDARIES:
            with self.subTest(utc=ts):
                self.assertIs(cme_session.weekend_closed(utc(ts)), want)

    def test_any_timezone_same_instant(self):
        # 2026-08-22（六）08:17 台北，todo6 實例
        self.assertTrue(cme_session.weekend_closed(utc("2026-08-22T00:17").astimezone(ZoneInfo("Asia/Taipei"))))

    def sweep(self, start, end, want):
        t = utc(start)
        while t < utc(end):
            self.assertIs(cme_session.weekend_closed(t), want, t.isoformat())
            t += timedelta(minutes=15)

    def test_open_week_never_closed(self):
        self.sweep("2026-10-18T22:00", "2026-10-23T21:00", False)  # 週日 18:00 至週五 17:00 EDT 前

    def test_whole_weekend_closed(self):
        self.sweep("2026-10-23T21:00", "2026-10-25T22:00", True)   # 週五 17:00 至週日 18:00 EDT 前


class CheckEsSessionTest(unittest.TestCase):
    """同一假時鐘下比對原版（BASELINE_REF）與新版 check_es.py 的輸出。"""

    WEEKDAY = [  # UTC；註解為台北時間（原版標籤依台北鐘點判定）
        "2026-10-20T21:30",  # 週三 05:30 US_AFTERHOURS
        "2026-10-20T22:00",  # 週三 06:00 ASIA_THIN
        "2026-10-21T07:00",  # 週三 15:00 EUROPE
        "2026-10-21T13:10",  # 週三 21:10 US_PREOPEN
        "2026-10-21T13:30",  # 週三 21:30 US_REGULAR
        "2026-10-21T19:59",  # 週四 03:59 US_REGULAR
        "2026-10-21T20:00",  # 週四 04:00 US_AFTERHOURS
        "2026-10-23T20:59",  # 週六 04:59＝紐約週五 16:59（休市前）
        "2026-10-25T22:00",  # 週一 06:00＝紐約週日 18:00（已開盤）
    ]
    WEEKEND = [
        "2026-10-23T21:00",  # 紐約週五 17:00（台北週六 05:00，原版標 US_AFTERHOURS）
        "2026-08-22T00:17",  # 台北週六 08:17（todo6 實例，原版標 ASIA_THIN）
        "2026-10-25T21:59",  # 紐約週日 17:59（台北週一 05:59，原版標 US_AFTERHOURS）
    ]

    @classmethod
    def setUpClass(cls):
        fx = harness.es_fixture()
        base = harness.has_baseline()
        cls.runs = {}
        for args, out in (((), "es_check.txt"), (("--symbol", "ndx"), "ndx_es_check.txt")):
            for ts in cls.WEEKDAY + cls.WEEKEND:
                if args and ts not in (cls.WEEKDAY[1], cls.WEEKEND[0]):
                    continue
                old = harness.run("check_es.py", fx, args, ref=harness.BASELINE_REF, now_utc=ts,
                                  files=harness.ES_FILES) if base else None
                new = harness.run("check_es.py", fx, args, now_utc=ts, files=harness.ES_FILES)
                cls.runs[(out, ts)] = (old, new)

    def load(self, r, out):
        self.assertEqual(r.code, 0, r.out + r.err)
        return json.loads(r.files[out])

    def test_weekday_output_identical(self):
        labels = set()
        for (out, ts), (old, new) in self.runs.items():
            if ts not in self.WEEKDAY:
                continue
            if old is None:
                self.skipTest("找不到基準版本 %s" % harness.BASELINE_REF)
            with self.subTest(out=out, utc=ts):
                self.assertEqual(new.code, old.code)
                self.assertEqual(new.out, old.out)
                self.assertEqual(new.files[out], old.files[out])
                labels.add(self.load(new, out)["session"]["label"])
        self.assertEqual(labels, {"US_AFTERHOURS", "ASIA_THIN", "EUROPE", "US_PREOPEN", "US_REGULAR"})

    def test_weekend_label(self):
        for (out, ts), (old, new) in self.runs.items():
            if ts not in self.WEEKEND:
                continue
            with self.subTest(out=out, utc=ts):
                d = self.load(new, out)
                self.assertEqual(d["session"]["label"], "WEEKEND_CLOSED")
                self.assertIn(NOTE, d["session"]["note"])
                if old is None:
                    continue
                o = self.load(old, out)
                self.assertNotEqual(o["session"]["label"], "WEEKEND_CLOSED")
                if o["session"]["label"] == "US_AFTERHOURS":
                    self.assertEqual({k: v for k, v in d.items() if k != "session"},
                                     {k: v for k, v in o.items() if k != "session"})

    def test_ndx_does_not_touch_spx_file(self):
        for (out, ts), (old, new) in self.runs.items():
            if out == "ndx_es_check.txt":
                self.assertNotIn("es_check.txt", new.files)


if __name__ == "__main__":
    unittest.main()
