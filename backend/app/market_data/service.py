"""Unified market data access for analysis engines."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

import pandas as pd

from app.market_data.freshness import freshness_tracker
from app.market_data.normalizer import validate_ohlcv
from app.market_data.providers.base import MarketDataProvider
from app.market_data.providers.binance import BinanceProvider, use_binance
from app.market_data.providers.fallback import FallbackProvider
from app.market_data.providers.kraken import KrakenProvider
from app.market_data.providers.router import AssetRouterProvider
from app.market_data.types import DerivativesSnapshot, TickerSnapshot
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_OHLCV_CACHE: TTLCache[pd.DataFrame] = TTLCache(ttl_seconds=180.0)
_CHART_OHLCV_CACHE: TTLCache[pd.DataFrame] = TTLCache(ttl_seconds=30.0)
_TICKER_CACHE: TTLCache[TickerSnapshot] = TTLCache(ttl_seconds=60.0)
_CHART_TIMEFRAMES = frozenset({"1m", "5m", "15m"})
_DERIVATIVES_CACHE: TTLCache[DerivativesSnapshot] = TTLCache(ttl_seconds=120.0)
_WARM_WORKERS = 16


def build_default_provider() -> MarketDataProvider:
    """Build provider router: crypto via Kraken→Binance→depth, equities via Yahoo.

    Render/US IPs get Binance 451 — skip it there. Kraken covers spot.
    Funding/OI come from Binance (when allowed), Bybit, then OKX (US/Render-safe).
    Local/EU can still append Binance for spot + futures.
    """
    from app.market_data.providers.depth_derivatives import DepthDerivativesProvider

    chain: list[MarketDataProvider] = [KrakenProvider(timeout=5.0)]
    if use_binance():
        chain.append(BinanceProvider(timeout=1.0))
    chain.append(DepthDerivativesProvider())
    return AssetRouterProvider(crypto=FallbackProvider(chain))


def _ohlcv_observed_at(df: pd.DataFrame) -> datetime | None:
    """Extract the last candle timestamp from an OHLCV frame."""
    if df is None or df.empty or "timestamp" not in df.columns:
        return None
    raw = df["timestamp"].iloc[-1]
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    try:
        ts = pd.Timestamp(raw)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return ts.to_pydatetime()
    except (TypeError, ValueError):
        return None


class MarketDataService:
    """Unified market data access for analysis engines."""

    def __init__(self, provider: MarketDataProvider | None = None) -> None:
        """Initialize with a data provider; defaults to Binance → Kraken fallback."""
        self._provider = provider or build_default_provider()

    def warm(self, symbols: list[str], timeframe: str = "1h", limit: int = 200) -> None:
        """Prefetch OHLCV for shared benchmarks and listed symbols (parallel)."""
        if not symbols:
            return
        if len(symbols) == 1:
            self.safe_get_ohlcv(symbols[0], timeframe, limit)
            return
        workers = min(len(symbols), _WARM_WORKERS)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(self.safe_get_ohlcv, symbol, timeframe, limit)
                for symbol in symbols
            ]
            for future in as_completed(futures):
                future.result()  # safe_get_ohlcv already swallows errors

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
            try:
                raw = self._provider.get_ohlcv(symbol, timeframe, limit)
            except Exception:
                freshness_tracker.record_failure(symbol)
                raise
            if raw is None or (isinstance(raw, pd.DataFrame) and raw.empty):
                freshness_tracker.record_failure(symbol)
                msg = f"Empty OHLCV for {symbol}"
                raise ValueError(msg)
            freshness_tracker.record_success(
                symbol,
                observed_at=_ohlcv_observed_at(raw),
            )
            try:
                from app.data_lake.warehouse.ohlcv import persist_ohlcv_frame

                persist_ohlcv_frame(raw, symbol=symbol, timeframe=timeframe)
            except Exception:
                logger.debug("OHLCV warehouse persist skipped for %s", symbol, exc_info=True)
            return raw

        cache = _CHART_OHLCV_CACHE if timeframe in _CHART_TIMEFRAMES else _OHLCV_CACHE
        df = cache.get_or_set(cache_key, fetch)
        return validate_ohlcv(df.copy(), min_rows=min_rows)

    def get_ticker(self, symbol: str) -> TickerSnapshot:
        """Fetch latest ticker snapshot."""
        cache_key = f"ticker:{symbol.upper()}"

        def fetch() -> TickerSnapshot:
            try:
                ticker = self._provider.get_ticker(symbol)
            except Exception:
                freshness_tracker.record_failure(symbol)
                raise
            if ticker is None:
                freshness_tracker.record_failure(symbol)
                msg = f"Empty ticker for {symbol}"
                raise ValueError(msg)
            freshness_tracker.record_success(
                symbol,
                observed_at=ticker.timestamp,
            )
            return ticker

        return _TICKER_CACHE.get_or_set(cache_key, fetch)

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
