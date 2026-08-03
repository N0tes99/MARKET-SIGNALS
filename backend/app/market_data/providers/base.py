"""Market data provider protocol."""

from typing import Protocol

import pandas as pd

from app.market_data.types import DerivativesSnapshot, TickerSnapshot


class MarketDataProvider(Protocol):
    """Interface for exchange and data feed adapters."""

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
        """Return OHLCV data as a DataFrame with standard columns."""
        ...

    def get_ticker(self, symbol: str) -> TickerSnapshot:
        """Return the latest price snapshot."""
        ...

    def get_derivatives(self, symbol: str) -> DerivativesSnapshot:
        """Return derivatives market data for the symbol."""
        ...
