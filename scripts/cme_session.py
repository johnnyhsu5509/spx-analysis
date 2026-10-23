"""CME 週末休市判定（rules_todo todo6）。

休市窗口：週五 17:00 ET 收盤至週日 18:00 ET 開盤，以 America/New_York 當地時間判定（夏令時間由 zoneinfo 處理）。
國定假日不處理。
"""
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def weekend_closed(ts):
    """ts 為帶時區的 datetime。"""
    t = ts.astimezone(NY)
    wd = t.weekday()
    return wd == 5 or (wd == 4 and t.hour >= 17) or (wd == 6 and t.hour < 18)
