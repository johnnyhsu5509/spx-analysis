"""測試執行器：python run.py <script> [args]。同目錄的假 yfinance 會優先於真的被 import。

設 FAKE_NOW_UTC（ISO 時間，UTC）時固定 datetime.now()：帶 tz 回傳該時刻，不帶 tz 回傳本機牆鐘時間。
本機時區預設台北（模擬 Johnny 的電腦）；FAKE_LOCAL_TZ=UTC 模擬 GitHub Actions runner。
"""
import os
import runpy
import sys

if os.environ.get("FAKE_NOW_UTC"):
    import datetime as _dt
    from zoneinfo import ZoneInfo

    import pandas  # noqa: F401  先載入，讓 pandas 綁定真正的 datetime 類別

    _AT = _dt.datetime.fromisoformat(os.environ["FAKE_NOW_UTC"]).replace(tzinfo=_dt.timezone.utc)
    _LOCAL = ZoneInfo(os.environ.get("FAKE_LOCAL_TZ") or "Asia/Taipei")

    class _Clock(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return _AT.astimezone(tz) if tz else _AT.astimezone(_LOCAL).replace(tzinfo=None)

    _dt.datetime = _Clock

sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
