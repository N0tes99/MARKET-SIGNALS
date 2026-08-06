"""Unified market data access for analysis engines."""

import logging

import pandas as pd

from app.market_data.normalizer import validate_ohlcv
from app.market_data.providers.base import MarketDataProvider
from app.market_data.providers.binance import BinanceProvider
from app.market_data.providers.fallback import FallbackProvider
from app.market_data.providers.kraken import KrakenProvider
from app.market_data.providers.router import AssetRouterProvider
from app.market_data.types import DerivativesSnapshot, TickerSnapshot
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_OHLCV_CACHE: TTLCache[pd.DataFrame] = TTLCache(ttl_seconds=180.0)
_TICKER_CACHE: TTLCache[TickerSnapshot] = TTLCache(ttl_seconds=60.0)
_DERIVATIVES_CACHE: TTLCache[DerivativesSnapshot] = TTLCache(ttl_seconds=120.0)


def build_default_provider() -> MarketDataProvider:
    """Build provider router: crypto via Kraken→Binance, equities via Yahoo.

    Render/US IPs usually get Binance 403/451. Trying Kraken first avoids a
    wasted ~1–1.5s timeout on almost every cold crypto OHLCV call.
    """
    crypto = FallbackProvider(
        [KrakenProvider(timeout=5.0), BinanceProvider(timeout=1.0)]
    )
    return AssetRouterProvider(crypto=crypto)


class MarketDataService:
    """Unified market data access for analysis engines."""

    def __init__(self, provider: MarketDataProvider | None = None) -> None:
        """Initialize with a data provider; defaults to Binance → Kraken fallback."""
        self._provider = provider or build_default_provider()

    def warm(self, symbols: list[str], timeframe: str = "1h", limit: int = 200) -> None:
        """Prefetch OHLCV for shared benchmarks and listed symbols."""
        for symbol in symbols:
            self.safe_get_ohlcv(symbol, timeframe, limit)

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 200,
        min_rows: int = 50,
    ) -> pd.DataFrame:
        """Fetch and validate OHLCV data."""
        cache_key = f"ohlcv:{symbol.upper()}:{timeframe}:{limit}"

        def fetch() -> pd.DataFrame:
            return self._provider.get_ohlcv(symbol, timeframe, limit)

        df = _OHLCV_CACHE.get_or_set(cache_key, fetch)
        return validate_ohlcv(df.copy(), min_rows=min_rows)

    def get_ticker(self, symbol: str) -> TickerSnapshot:
        """Fetch latest ticker snapshot."""
        cache_key = f"ticker:{symbol.upper()}"
        return _TICKER_CACHE.get_or_set(
            cache_key,
            lambda: self._provider.get_ticker(symbol),
        )

    def get_derivatives(self, symbol: str) -> DerivativesSnapshot:
        """Fetch derivatives market snapshot."""
        cache_key = f"derivatives:{symbol.upper()}"
        return _DERIVATIVES_CACHE.get_or_set(
            cache_key,
            lambda: self._provider.get_derivatives(symbol),
        )

    def safe_get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 200,
    ) -> pd.DataFrame | None:
        """Fetch OHLCV without raising; returns None on failure."""
        try:
            return self.get_ohlcv(symbol, timeframe, limit, min_rows=20)
        except Exception:
            logger.exception("Failed to fetch OHLCV for %s", symbol)
            return None
