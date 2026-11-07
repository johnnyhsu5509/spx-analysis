import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import harness  # 須先 import：把 scripts/ 加入 sys.path
import cme_session

NOTE = "此為前一交易日結算值，非即時"
NY = ZoneInfo("America/New_York")
TPE = ZoneInfo("Asia/Taipei")
SEMI = {"es_check.txt": "semi_vs_spx", "ndx_es_check.txt": "semi_vs_ndx"}


def core(d):
    """去掉 H8 刻意改動的欄位（checked_at 時區、session、SOXX 即時判定），其餘應與原版逐字相同。"""
    return {k: v for k, v in d.items() if k not in ("checked_at", "session", "soxx_semis", "semi_vs_spx", "semi_vs_ndx")}


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
    """同一假時鐘下比對原版（ES_BASELINE_REF，WEEKEND_CLOSED 加入前）與新版 check_es.py 的輸出。"""

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
        base = harness.has_baseline(harness.ES_BASELINE_REF, "check_es.py")
        cls.runs = {}
        for args, out in (((), "es_check.txt"), (("--symbol", "ndx"), "ndx_es_check.txt")):
            for ts in cls.WEEKDAY + cls.WEEKEND:
                if args and ts not in (cls.WEEKDAY[1], cls.WEEKEND[0]):
                    continue
                old = harness.run("check_es.py", fx, args, ref=harness.ES_BASELINE_REF, now_utc=ts,
                                  files=harness.ES_FILES) if base else None
                new = harness.run("check_es.py", fx, args, now_utc=ts, files=harness.ES_FILES)
                cls.runs[(out, ts)] = (old, new)

    def load(self, r, out):
        self.assertEqual(r.code, 0, r.out + r.err)
        return json.loads(r.files[out])

    def test_summer_weekday_matches_baseline(self):
        """以上時刻都在夏令（EDT）：時段標籤須與原版（台北鐘點）相同，SOXX 以外的輸出逐字相同。"""
        labels = set()
        for (out, ts), (old, new) in self.runs.items():
            if ts not in self.WEEKDAY:
                continue
            if old is None:
                self.skipTest("找不到基準版本 %s" % harness.ES_BASELINE_REF)
            with self.subTest(out=out, utc=ts):
                self.assertEqual(new.code, old.code)
                self.assertEqual(new.out, old.out)
                d, o = self.load(new, out), self.load(old, out)
                self.assertEqual(d["session"]["label"], o["session"]["label"])
                self.assertEqual(core(d), core(o))
                if d["session"]["label"] == "US_REGULAR":  # 盤中 SOXX 讀數與背離不變
                    self.assertEqual(d["soxx_semis"], o["soxx_semis"])
                    self.assertEqual(d[SEMI[out]], o[SEMI[out]])
                labels.add(d["session"]["label"])
        self.assertEqual(labels, {"US_AFTERHOURS", "ASIA_THIN", "EUROPE", "US_PREOPEN", "US_REGULAR"})

    def test_weekend_label(self):
        for (out, ts), (old, new) in self.runs.items():
            if ts not in self.WEEKEND:
                continue
            with self.subTest(out=out, utc=ts):
                d = self.load(new, out)
                self.assertEqual(d["session"]["label"], "WEEKEND_CLOSED")
                self.assertIn(NOTE, d["session"]["note"])
                self.assertIs(d["soxx_semis"].get("stale"), True)
                self.assertNotIn(SEMI[out], d)
                if old is None:
                    continue
                o = self.load(old, out)
                self.assertNotEqual(o["session"]["label"], "WEEKEND_CLOSED")
                if o["session"]["label"] == "US_AFTERHOURS":
                    self.assertEqual(core(d), core(o))

    def test_ndx_does_not_touch_spx_file(self):
        for (out, ts), (old, new) in self.runs.items():
            if out == "ndx_es_check.txt":
                self.assertNotIn("es_check.txt", new.files)


class CheckEsNyClockTest(unittest.TestCase):
    """H8：時段依紐約時間判定（夏令／冬令由 zoneinfo 處理），與本機時區無關；SOXX 只在美股盤中算即時。"""

    # (UTC 時刻, 預期標籤)；註解為 台北／紐約 當地時間
    WINTER = [  # 2026-11-01 起 EST(UTC-5)，台北＝紐約＋13h
        ("2026-11-05T06:30", "ASIA_THIN"),      # 台北 14:30／紐約 01:30（稽核 E4）
        ("2026-11-05T08:00", "EUROPE"),         # 台北 16:00／紐約 03:00
        ("2026-11-05T13:10", "EUROPE"),         # 台北 21:10／紐約 08:10（稽核 E4：原版 US_PREOPEN＋假背離）
        ("2026-11-05T13:20", "EUROPE"),         # 台北 21:20／紐約 08:20（SKILL 的 21:20 期貨確認）
        ("2026-11-05T13:40", "EUROPE"),         # 台北 21:40／紐約 08:40（原版誤標 US_REGULAR）
        ("2026-11-05T14:00", "US_PREOPEN"),     # 台北 22:00／紐約 09:00（稽核 E4：原版 US_REGULAR）
        ("2026-11-05T14:29", "US_PREOPEN"),     # 台北 22:29／紐約 09:29
        ("2026-11-05T14:30", "US_REGULAR"),     # 台北 22:30／紐約 09:30 開盤
        ("2026-11-05T20:59", "US_REGULAR"),     # 台北 04:59／紐約 15:59
        ("2026-11-05T21:00", "US_AFTERHOURS"),  # 台北 05:00／紐約 16:00
        ("2026-11-05T22:59", "US_AFTERHOURS"),  # 台北 06:59／紐約 17:59（原版標 ASIA_THIN）
        ("2026-11-05T23:00", "ASIA_THIN"),      # 台北 07:00／紐約 18:00
        ("2026-11-06T07:59", "ASIA_THIN"),      # 台北 15:59／紐約 02:59（原版標 EUROPE）
    ]
    SUMMER = [  # EDT(UTC-4)，台北＝紐約＋12h：分界與原版的台北鐘點相同
        ("2026-10-21T12:59", "EUROPE"),         # 台北 20:59／紐約 08:59
        ("2026-10-21T13:00", "US_PREOPEN"),     # 台北 21:00／紐約 09:00
        ("2026-10-21T13:20", "US_PREOPEN"),     # 台北 21:20／紐約 09:20（SKILL 的 21:20 期貨確認）
        ("2026-10-21T13:29", "US_PREOPEN"),     # 台北 21:29／紐約 09:29
        ("2026-10-21T13:30", "US_REGULAR"),     # 台北 21:30／紐約 09:30
        ("2026-10-21T19:59", "US_REGULAR"),     # 台北 03:59／紐約 15:59
        ("2026-10-21T20:00", "US_AFTERHOURS"),  # 台北 04:00／紐約 16:00
        ("2026-10-21T21:59", "US_AFTERHOURS"),  # 台北 05:59／紐約 17:59
        ("2026-10-21T22:00", "ASIA_THIN"),      # 台北 06:00／紐約 18:00
        ("2026-10-22T06:59", "ASIA_THIN"),      # 台北 14:59／紐約 02:59
        ("2026-10-22T07:00", "EUROPE"),         # 台北 15:00／紐約 03:00
    ]
    SWITCH = [  # 換季前後的交易日
        ("2026-03-06T14:29", "US_PREOPEN"),     # 週五 台北 22:29／紐約 09:29 EST
        ("2026-03-06T14:30", "US_REGULAR"),     # 週五 台北 22:30／紐約 09:30 EST
        ("2026-03-09T13:30", "US_REGULAR"),     # 週一 台北 21:30／紐約 09:30 EDT（3/8 已進夏令）
        ("2026-11-02T13:30", "EUROPE"),         # 週一 台北 21:30／紐約 08:30 EST（11/1 已出夏令）
        ("2026-11-02T14:30", "US_REGULAR"),     # 週一 台北 22:30／紐約 09:30 EST
    ]
    NDX = ("2026-11-05T13:20", "2026-11-05T14:00", "2026-11-05T14:30", "2026-10-21T13:20")
    ACTIONS = [  # 本機時區＝UTC（GitHub Actions runner）
        ("2026-11-05T01:29", "ASIA_THIN"),      # data/es_check.txt 實例：紐約 11/04 20:29，原版在 runner 上標 US_REGULAR
        ("2026-11-05T21:15", "US_AFTERHOURS"),  # Actions 冬令排程 21:15 UTC＝紐約 16:15
        ("2026-10-21T21:15", "US_AFTERHOURS"),  # Actions 夏令排程 21:15 UTC＝紐約 17:15
        ("2026-11-05T14:00", "US_PREOPEN"),     # 紐約 09:00
    ]

    @classmethod
    def setUpClass(cls):
        fx = harness.es_fixture()
        base = harness.has_baseline(harness.ES_BASELINE_REF, "check_es.py")
        jobs = {("spx", ts, None, None): ((), ts, None, None) for ts, _ in cls.WINTER + cls.SUMMER + cls.SWITCH}
        jobs.update({("ndx", ts, None, None): (("--symbol", "ndx"), ts, None, None) for ts in cls.NDX})
        for ts, _ in cls.ACTIONS:
            jobs[("spx", ts, None, None)] = ((), ts, None, None)
            jobs[("spx", ts, "UTC", None)] = ((), ts, "UTC", None)
        if base:
            ref = harness.ES_BASELINE_REF
            jobs[("spx", "2026-11-05T14:00", None, ref)] = ((), "2026-11-05T14:00", None, ref)
            jobs[("spx", "2026-11-05T01:29", "UTC", ref)] = ((), "2026-11-05T01:29", "UTC", ref)
        cls.base = base

        def go(job):
            args, ts, tz, ref = job
            return harness.run("check_es.py", fx, args, ref=ref, now_utc=ts, files=harness.ES_FILES, local_tz=tz)

        with ThreadPoolExecutor(max_workers=6) as ex:
            cls.runs = dict(zip(jobs, ex.map(go, jobs.values())))

    def load(self, key):
        r = self.runs[key]
        out = "ndx_es_check.txt" if key[0] == "ndx" else "es_check.txt"
        self.assertEqual(r.code, 0, r.out + r.err)
        return json.loads(r.files[out])

    def test_labels(self):
        for ts, want in self.WINTER + self.SUMMER + self.SWITCH:
            with self.subTest(utc=ts):
                s = self.load(("spx", ts, None, None))["session"]
                self.assertEqual(s["label"], want)
                ny = utc(ts).astimezone(NY)
                self.assertEqual(s["ny_time"], ny.strftime("%Y-%m-%d %H:%M ") + ("EDT" if ny.dst() else "EST"))

    def test_winter_open_is_2230_taipei(self):
        """冬令台北 21:30–22:30 不得標盤中（H8 情境 a）。"""
        for ts, _ in self.WINTER:
            tpe = utc(ts).astimezone(TPE)
            if (21, 30) <= (tpe.hour, tpe.minute) < (22, 30):
                with self.subTest(utc=ts):
                    self.assertNotEqual(self.load(("spx", ts, None, None))["session"]["label"], "US_REGULAR")

    def test_soxx_live_only_in_regular_session(self):
        for key in self.runs:
            if key[3] is not None:
                continue
            with self.subTest(key=key):
                d = self.load(key)
                semi = "semi_vs_ndx" if key[0] == "ndx" else "semi_vs_spx"
                if d["session"]["label"] == "US_REGULAR":
                    self.assertNotIn("stale", d["soxx_semis"])
                    self.assertIn(semi, d)
                else:  # 含 US_PREOPEN（H8 情境 b）
                    self.assertIs(d["soxx_semis"]["stale"], True)
                    self.assertIn("非即時", d["soxx_semis"]["note"])
                    self.assertNotIn(semi, d)

    def test_checked_at_has_taipei_offset(self):
        for key in self.runs:
            if key[3] is not None:
                continue
            with self.subTest(key=key):
                want = utc(key[1]).astimezone(TPE).isoformat(sep=" ", timespec="minutes")
                self.assertEqual(self.load(key)["checked_at"], want)
                self.assertTrue(want.endswith("+08:00"))

    def test_ndx_same_session_and_own_file(self):
        for ts in self.NDX:
            with self.subTest(utc=ts):
                r = self.runs[("ndx", ts, None, None)]
                self.assertNotIn("es_check.txt", r.files)
                self.assertEqual(self.load(("ndx", ts, None, None))["session"],
                                 self.load(("spx", ts, None, None))["session"])

    def test_actions_utc_clock_same_output(self):
        """H8 情境 c：本機時區不同（台北／UTC），同一時刻的輸出逐字相同。"""
        for ts, want in self.ACTIONS:
            with self.subTest(utc=ts):
                tw, gh = self.runs[("spx", ts, None, None)], self.runs[("spx", ts, "UTC", None)]
                self.assertEqual(gh.code, 0, gh.out + gh.err)
                self.assertEqual(gh.files["es_check.txt"], tw.files["es_check.txt"])
                self.assertEqual(self.load(("spx", ts, "UTC", None))["session"]["label"], want)

    def test_baseline_reproduces_h8(self):
        """原版在同樣時刻確實標錯（證明上面的測試抓得到這個 bug）。"""
        if not self.base:
            self.skipTest("找不到基準版本 %s" % harness.ES_BASELINE_REF)
        ref = harness.ES_BASELINE_REF
        d = self.load(("spx", "2026-11-05T14:00", None, ref))
        self.assertEqual(d["session"]["label"], "US_REGULAR")
        self.assertIn("semi_vs_spx", d)
        self.assertEqual(self.load(("spx", "2026-11-05T01:29", "UTC", ref))["session"]["label"], "US_REGULAR")


if __name__ == "__main__":
    unittest.main()
