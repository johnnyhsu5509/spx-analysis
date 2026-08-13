# -*- coding: utf-8 -*-
"""yfinance transport shim.

yfinance 1.x uses curl_cffi with browser TLS impersonation, which avoids
Yahoo's bot rate-limiting. Some sandboxed/cloud environments MITM TLS at
the egress proxy; the impersonated handshake is then reset
("curl: (35) Recv failure: Connection reset by peer").

Strategy: always try the default transport first (best Yahoo compatibility),
and only on failure retry once through a plain requests.Session, which
survives MITM but is more likely to be rate-limited.

Force the plain transport from the start with SPX_HTTP_PLAIN=1.
ASCII-only output (cp950 safe).
"""
import os

_FORCE_PLAIN = os.environ.get('SPX_HTTP_PLAIN', '').strip().lower() not in ('', '0', 'false', 'no')


def _plain_session():
    import requests
    return requests.Session()


def _empty(df):
    return df is None or getattr(df, 'empty', False)


def download(*args, **kwargs):
    """yf.download with automatic plain-requests fallback."""
    import yfinance as yf
    if _FORCE_PLAIN:
        kwargs.setdefault('session', _plain_session())
        return yf.download(*args, **kwargs)
    try:
        df = yf.download(*args, **kwargs)
        if not _empty(df):
            return df
    except Exception:
        pass
    print('[yf_compat] default transport failed, retrying via plain requests')
    kwargs['session'] = _plain_session()
    return yf.download(*args, **kwargs)


def ticker(symbol):
    """yf.Ticker honouring SPX_HTTP_PLAIN (no auto-retry: failure surfaces later)."""
    import yfinance as yf
    if _FORCE_PLAIN:
        return yf.Ticker(symbol, session=_plain_session())
    return yf.Ticker(symbol)


def history(symbol, **kwargs):
    """Ticker(...).history(...) with automatic plain-requests fallback."""
    import yfinance as yf
    if _FORCE_PLAIN:
        return yf.Ticker(symbol, session=_plain_session()).history(**kwargs)
    try:
        df = yf.Ticker(symbol).history(**kwargs)
        if not _empty(df):
            return df
    except Exception:
        pass
    print('[yf_compat] default transport failed, retrying via plain requests')
    return yf.Ticker(symbol, session=_plain_session()).history(**kwargs)
