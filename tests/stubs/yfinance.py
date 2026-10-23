"""測試用假 yfinance：資料一律來自 YF_FIXTURE 指向的 pickle，不連網。"""
import os
import pickle

import pandas as pd

with open(os.environ["YF_FIXTURE"], "rb") as _f:
    _FX = pickle.load(_f)


def _frame(ticker, interval):
    if _FX.get("mode") == "raise":
        raise ConnectionError("synthetic network failure")
    kind = "daily" if interval == "1d" else "intraday"
    return _FX[kind].get(ticker, pd.DataFrame()).copy()


def download(ticker, interval="1d", **kwargs):
    return _frame(ticker, interval)


class Ticker:
    def __init__(self, symbol, session=None):
        self.symbol = symbol

    @property
    def fast_info(self):
        last, prev = _FX["quote"][self.symbol]
        return {"last_price": last, "previous_close": prev}

    def history(self, interval="1d", **kwargs):
        return _frame(self.symbol, interval)
