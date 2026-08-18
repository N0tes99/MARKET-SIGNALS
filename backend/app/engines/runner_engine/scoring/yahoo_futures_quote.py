"""Small Yahoo .info snapshot for CME continuous futures — not the 13-dim radar pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime

import yfinance as yf

from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_QUOTE_CACHE: TTLCache[YahooFuturesQuote] = TTLCache(ttl_seconds=180.0)


@dataclass(frozen=True)
class YahooFuturesQuote:
    """Free Yahoo fields used by the CME board. None = field not present."""

    symbol: str
    fetched_ok: bool
    last: float | None = None
    change_pct: float | None = None
    volume: float | None = None
    open_interest: float | None = None
    expire_date: date | None = None


def _num(info: dict, *keys: str) -> float | None:
    for key in keys:
        raw = info.get(key)
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


def _expire_date(info: dict) -> date | None:
    raw = info.get("expireDate")
    if raw is None:
        raw = info.get("expirationDate")
    if raw is None:
        return None
    try:
        ts = float(raw)
    except (TypeError, ValueError):
        return None
    if ts <= 0:
        return None
    if ts > 1e12:
        ts /= 1000.0
    try:
        return datetime.fromtimestamp(ts, UTC).date()
    except (OverflowError, OSError, ValueError):
        return None


def empty_yahoo_futures_quote(symbol: str) -> YahooFuturesQuote:
    """Explicit miss — used by tests and failed fetches."""
    return YahooFuturesQuote(symbol=symbol.upper().strip(), fetched_ok=False)


def _parse_info(symbol: str, info: dict) -> YahooFuturesQuote:
    last = _num(info, "regularMarketPrice", "previousClose")
    change = _num(info, "regularMarketChangePercent")
    volume = _num(info, "regularMarketVolume", "volume")
    oi = _num(info, "openInterest")
    return YahooFuturesQuote(
        symbol=symbol,
        fetched_ok=True,
        last=last if last is not None and last > 0 else None,
        change_pct=change,
        volume=volume if volume is not None and volume >= 0 else None,
        open_interest=oi if oi is not None and oi >= 0 else None,
        expire_date=_expire_date(info),
    )


def fetch_yahoo_futures_quote(symbol: str) -> YahooFuturesQuote:
    """Cached Yahoo ``.info`` slice for one continuous futures root."""
    normalized = symbol.upper().strip()
    cached = _QUOTE_CACHE.get(normalized)
    if cached is not None:
        return cached

    try:
        ticker = yf.Ticker(normalized)
        raw_info = ticker.info
        info = raw_info if isinstance(raw_info, dict) else {}
        snap = _parse_info(normalized, info) if info else empty_yahoo_futures_quote(normalized)
    except Exception:
        logger.warning("Yahoo futures quote failed for %s", normalized, exc_info=True)
        snap = empty_yahoo_futures_quote(normalized)

    _QUOTE_CACHE.set(normalized, snap)
    return snap


def clear_yahoo_futures_quote_cache() -> None:
    """Test helper."""
    _QUOTE_CACHE.clear()
