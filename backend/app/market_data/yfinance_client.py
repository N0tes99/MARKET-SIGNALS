"""Load yfinance only when a Yahoo call actually runs.

Importing yfinance at module level pulled curl_cffi / pandas extras into the
uvicorn bind path and delayed the first /health after a Render sleep.
"""

from __future__ import annotations


def yf_ticker(symbol: str):
    import yfinance as yf

    return yf.Ticker(symbol)
