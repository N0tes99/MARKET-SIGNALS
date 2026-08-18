"""Small Yahoo ``fast_info`` snapshot for CME continuous futures — not ``.info``."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import yfinance as yf

from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_QUOTE_CACHE: TTLCache[YahooFuturesQuote] = TTLCache(ttl_seconds=180.0)


@dataclass(frozen=True)
class YahooFuturesQuote:
    """Free Yahoo fields used by the CME board. None = field not present.

    ``open_interest`` and ``expire_date`` stay optional — ``fast_info`` does
    not expose them. Do not invent values.
    """

    symbol: str
    fetched_ok: bool
    last: float | None = None
    change_pct: float | None = None
    volume: float | None = None
    open_interest: float | None = None
    expire_date: date | None = None


def _fast_get(info: object, key: str) -> object:
    if isinstance(info, dict):
        return info.get(key)
    return getattr(info, key, None)


def _fast_num(info: object, *keys: str) -> float | None:
    for key in keys:
        raw = _fast_get(info, key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value != value:  # NaN
            continue
        return value
    return None


def empty_yahoo_futures_quote(symbol: str) -> YahooFuturesQuote:
    """Explicit miss — used by tests and failed fetches."""
    return YahooFuturesQuote(symbol=symbol.upper().strip(), fetched_ok=False)


def _parse_fast_info(symbol: str, info: object) -> YahooFuturesQuote:
    last = _fast_num(info, "last_price", "regular_market_price")
    prev = _fast_num(info, "previous_close", "regular_market_previous_close")
    volume = _fast_num(info, "last_volume", "regular_market_volume", "ten_day_average_volume")
    change = None
    if last is not None and prev is not None and prev > 0:
        change = (last / prev - 1.0) * 100.0
    last = last if last is not None and last > 0 else None
    volume = volume if volume is not None and volume >= 0 else None
    if last is None and volume is None and change is None:
        return empty_yahoo_futures_quote(symbol)
    return YahooFuturesQuote(
        symbol=symbol,
        fetched_ok=True,
        last=last,
        change_pct=change,
        volume=volume,
        open_interest=None,
        expire_date=None,
    )


def fetch_yahoo_futures_quote(symbol: str) -> YahooFuturesQuote:
    """Cached Yahoo ``fast_info`` slice for one continuous futures root."""
    normalized = symbol.upper().strip()
    cached = _QUOTE_CACHE.get(normalized)
    if cached is not None:
        return cached

    try:
        ticker = yf.Ticker(normalized)
        snap = _parse_fast_info(normalized, ticker.fast_info)
    except Exception:
        logger.warning("Yahoo futures quote failed for %s", normalized, exc_info=True)
        snap = empty_yahoo_futures_quote(normalized)

    _QUOTE_CACHE.set(normalized, snap)
    return snap


def clear_yahoo_futures_quote_cache() -> None:
    """Test helper."""
    _QUOTE_CACHE.clear()
