"""Lightweight price feeds for tracked assets."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.api.tracked import TRACKED_SYMBOLS
from app.core.process_limits import OHLCV_WARM_WORKERS
from app.market_data.service import MarketDataService
from app.schemas.quotes import AssetQuote
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_QUOTES_CACHE: TTLCache[list[AssetQuote]] = TTLCache(ttl_seconds=90.0)
_MAX_WORKERS = OHLCV_WARM_WORKERS


def build_quote(market_data: MarketDataService, symbol: str) -> AssetQuote:
    """Fetch last price only — no OHLCV (keeps /quotes under proxy timeouts)."""
    normalized = symbol.upper()
    try:
        ticker = market_data.get_ticker(normalized)
        return AssetQuote(
            symbol=normalized,
            price=float(ticker.price),
            change_pct=None,
            as_of=ticker.timestamp,
            available=True,
        )
    except Exception:
        logger.debug("Ticker unavailable for %s", normalized, exc_info=True)
        return AssetQuote(
            symbol=normalized,
            price=None,
            change_pct=None,
            as_of=None,
            available=False,
        )


def load_all_quotes(
    market_data: MarketDataService,
    *,
    progressive: bool = False,
) -> list[AssetQuote]:
    """Load quotes for the full watchlist (parallel, SWR-cached).

    ``progressive=True`` returns placeholders immediately on a cold cache so
    the dashboard is not blocked behind 61 ticker HTTP calls.
    """

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
                    logger.debug("Quote failed for %s", symbol, exc_info=True)
                    quotes[symbol] = AssetQuote(symbol=symbol.upper(), available=False)
        return [quotes[s] for s in TRACKED_SYMBOLS if s in quotes]

    if progressive:
        cached, _, _, _ = _QUOTES_CACHE.meta("all")
        if cached is None:
            _QUOTES_CACHE.seed_stale(
                "all",
                [AssetQuote(symbol=symbol, available=False) for symbol in TRACKED_SYMBOLS],
            )

    return _QUOTES_CACHE.get_stale_while_revalidate("all", _load)
