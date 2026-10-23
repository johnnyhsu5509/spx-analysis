"""測試執行器：python run.py <script> [args]。同目錄的假 yfinance 會優先於真的被 import。

設 FAKE_NOW_UTC（ISO 時間，UTC）時固定 datetime.now()：帶 tz 回傳該時刻，不帶 tz 回傳台北牆鐘時間（模擬本機）。
"""
import os
import runpy
import sys

if os.environ.get("FAKE_NOW_UTC"):
    import datetime as _dt
    from zoneinfo import ZoneInfo

    import pandas  # noqa: F401  先載入，讓 pandas 綁定真正的 datetime 類別

    _AT = _dt.datetime.fromisoformat(os.environ["FAKE_NOW_UTC"]).replace(tzinfo=_dt.timezone.utc)
    _TW = ZoneInfo("Asia/Taipei")

    class _Clock(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return _AT.astimezone(tz) if tz else _AT.astimezone(_TW).replace(tzinfo=None)

    _dt.datetime = _Clock

sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
