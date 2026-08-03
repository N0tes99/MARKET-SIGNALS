"""Market data provider with automatic fallback chain."""

import logging

import pandas as pd

from app.market_data.providers.base import MarketDataProvider
from app.market_data.types import DerivativesSnapshot, TickerSnapshot

logger = logging.getLogger(__name__)


class FallbackProvider:
    """Try multiple providers in order until one succeeds."""

    def __init__(self, providers: list[MarketDataProvider]) -> None:
        """Initialize with ordered list of providers to try."""
        if not providers:
            msg = "At least one market data provider is required"
            raise ValueError(msg)
        self._providers = providers

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
        """Fetch OHLCV from the first provider that succeeds."""
        errors: list[str] = []
        for provider in self._providers:
            name = type(provider).__name__
            try:
                return provider.get_ohlcv(symbol, timeframe, limit)
            except Exception as exc:
                logger.warning("%s OHLCV failed for %s: %s", name, symbol, exc)
                errors.append(f"{name}: {exc}")

        msg = f"All providers failed for {symbol}: {'; '.join(errors)}"
        raise RuntimeError(msg)

    def get_ticker(self, symbol: str) -> TickerSnapshot:
        """Fetch ticker from the first provider that succeeds."""
        for provider in self._providers:
            try:
                return provider.get_ticker(symbol)
            except Exception:
                logger.exception("%s ticker failed", type(provider).__name__)
        msg = f"All providers failed ticker for {symbol}"
        raise RuntimeError(msg)

    def get_derivatives(self, symbol: str) -> DerivativesSnapshot:
        """Fetch derivatives from the first provider that returns data."""
        for provider in self._providers:
            try:
                snapshot = provider.get_derivatives(symbol)
                if snapshot.funding_rate is not None or snapshot.open_interest is not None:
                    return snapshot
            except Exception:
                logger.exception("%s derivatives failed", type(provider).__name__)

        return DerivativesSnapshot(
            symbol=symbol.upper(),
            funding_rate=None,
            open_interest=None,
            mark_price=None,
        )
