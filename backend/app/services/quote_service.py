"""Lightweight price feeds for tracked assets."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

from app.api.tracked import TRACKED_SYMBOLS
from app.market_data.service import MarketDataService
from app.schemas.quotes import AssetQuote
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_QUOTES_CACHE: TTLCache[list[AssetQuote]] = TTLCache(ttl_seconds=45.0)
_MAX_WORKERS = 8


def _change_pct(last: float, prior: float) -> float | None:
    if prior == 0:
        return None
    return ((last - prior) / prior) * 100.0


def build_quote(market_data: MarketDataService, symbol: str) -> AssetQuote:
    """Fetch last price and approx % change for one symbol."""
    normalized = symbol.upper()
    price: float | None = None
    change: float | None = None
    as_of: datetime | None = None

    try:
        ticker = market_data.get_ticker(normalized)
        price = float(ticker.price)
        as_of = ticker.timestamp
    except Exception:
        logger.debug("Ticker unavailable for %s", normalized, exc_info=True)

    df = market_data.safe_get_ohlcv(normalized, timeframe="1d", limit=5)
    if df is None or len(df) < 2:
        df = market_data.safe_get_ohlcv(normalized, timeframe="1h", limit=30)

    if df is not None and len(df) >= 2:
        prior_close = float(df["close"].iloc[-2])
        last_close = float(df["close"].iloc[-1])
        if price is None:
            price = last_close
            as_of = datetime.now(UTC)
        change = _change_pct(price, prior_close)

    return AssetQuote(
        symbol=normalized,
        price=price,
        change_pct=change,
        as_of=as_of,
        available=price is not None,
    )


def load_all_quotes(market_data: MarketDataService) -> list[AssetQuote]:
    """Load quotes for the full watchlist (parallel, cached upstream)."""

    def _load() -> list[AssetQuote]:
        quotes: dict[str, AssetQuote] = {}
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            futures = {
                pool.submit(build_quote, market_data, symbol): symbol
                for symbol in TRACKED_SYMBOLS
            }
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    quotes[symbol] = future.result()
                except Exception:
                    logger.exception("Quote failed for %s", symbol)
                    quotes[symbol] = AssetQuote(symbol=symbol.upper(), available=False)
        return [quotes[s] for s in TRACKED_SYMBOLS if s in quotes]

    return _QUOTES_CACHE.get_or_set("all", _load)
