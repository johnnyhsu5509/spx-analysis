# -*- coding: utf-8 -*-
"""Cross-contamination guard for the SPX / NDX dual-system.

The four data scripts are shared between two systems and switch on --symbol.
Forgetting the flag makes an NDX run overwrite the SPX files, and SPX then
analyses NDX prices as if they were its own. That failure is silent: nothing
errors, the numbers just become wrong, and the ledgers are corrupted in a way
that cannot be reconstructed afterwards.

This module makes it loud instead.

  require_symbol(path, expected)  data file must carry the symbol we expect
  cross_check(base_dir)           the two systems' files must not hold the
                                  same close (that means one clobbered the other)
  stamp(result, symbol)           write the symbol into every output

Legacy tolerance: files written before the guard existed have no `symbol`
field. Those warn but pass; a symbol that is present and WRONG always aborts.

ASCII-only output (cp950 safe).
"""
import io
import json
import os
import sys

# canonical ticker per symbol -- used to catch a config edit that crosses wires
TICKERS = {"SPX": "^GSPC", "NDX": "^NDX"}
DATA_FILES = {"SPX": "today_data.txt", "NDX": "ndx_today_data.txt"}


def _die(lines):
    print("")
    print("=" * 68)
    print("GUARD ABORT -- cross-contamination risk")
    print("=" * 68)
    for l in lines:
        print(l)
    print("=" * 68)
    sys.exit(3)


def _load(path):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def stamp(result, symbol):
    """Embed the symbol so every later read can verify provenance."""
    result["symbol"] = symbol
    return result


def require_symbol(path, expected, what="data file"):
    """Abort if `path` carries a symbol other than `expected`."""
    d = _load(path)
    if d is None:
        return  # missing/unreadable is handled by the caller's own checks
    got = d.get("symbol")
    if got is None:
        print("[guard] NOTE: %s has no symbol field (pre-guard file); "
              "cannot verify provenance." % os.path.basename(path))
        return
    if str(got).upper() != expected.upper():
        _die([
            "%s: %s" % (what, path),
            "  expected symbol : %s" % expected,
            "  actual symbol   : %s" % got,
            "",
            "MEANING: this file belongs to the OTHER system. Almost certainly a",
            "         script was run without (or with the wrong) --symbol flag,",
            "         and it overwrote the file for %s." % expected,
            "",
            "FIX    : re-run the fetch for BOTH systems, in either order:",
            "           python3 fetch_today.py",
            "           python3 fetch_today.py --symbol ndx",
            "         then verify each output's trade_date and symbol before",
            "         doing any analysis.",
            "",
            "DO NOT : write to any ledger until both files carry the right symbol.",
        ])


def cross_check(base_dir):
    """Both systems' data files must not describe the same index.

    SPX and NDX never share a close price, so identical values mean one file
    overwrote the other.
    """
    a = _load(os.path.join(base_dir, DATA_FILES["SPX"]))
    b = _load(os.path.join(base_dir, DATA_FILES["NDX"]))
    if not a or not b:
        return
    ca, cb = a.get("close"), b.get("close")
    if ca is None or cb is None:
        return
    if abs(float(ca) - float(cb)) < 1e-9:
        _die([
            "today_data.txt and ndx_today_data.txt report the SAME close: %s" % ca,
            "",
            "MEANING: SPX and NDX cannot have an identical close. One file has",
            "         overwritten the other -- a --symbol flag was missed.",
            "",
            "FIX    : re-run both fetches and re-verify before analysing.",
        ])
    sa, sb = a.get("symbol"), b.get("symbol")
    if sa and sb and str(sa).upper() == str(sb).upper():
        _die([
            "Both data files carry symbol=%s." % sa,
            "one of them was written by the wrong invocation.",
            "FIX: re-run both fetches.",
        ])


def check_ticker(symbol, ticker):
    """Guard against a config edit that points a symbol at the wrong index."""
    want = TICKERS.get(symbol.upper())
    if want and ticker != want:
        _die([
            "symbol %s is configured to fetch %s, expected %s."
            % (symbol.upper(), ticker, want),
            "A SYMBOLS entry has been edited incorrectly -- refusing to fetch.",
        ])
