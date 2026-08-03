"""Synthetic market data provider for tests and offline development."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from app.market_data.normalizer import STANDARD_COLUMNS
from app.market_data.types import DerivativesSnapshot, TickerSnapshot


def generate_trending_ohlcv(
    rows: int = 200,
    start_price: float = 100.0,
    trend: float = 0.002,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic uptrending OHLCV data for testing."""
    rng = np.random.default_rng(seed)
    timestamps = [datetime.now(UTC) - timedelta(hours=rows - i) for i in range(rows)]

    closes = [start_price]
    for _ in range(rows - 1):
        noise = rng.normal(0, 0.005)
        closes.append(closes[-1] * (1 + trend + noise))

    data = []
    for i, close in enumerate(closes):
        high = close * (1 + abs(rng.normal(0, 0.003)))
        low = close * (1 - abs(rng.normal(0, 0.003)))
        open_price = closes[i - 1] if i > 0 else close
        volume = float(rng.uniform(800, 1500))
        data.append(
            {
                "timestamp": timestamps[i],
                "open": open_price,
                "high": max(high, open_price, close),
                "low": min(low, open_price, close),
                "close": close,
                "volume": volume,
            }
        )

    return pd.DataFrame(data, columns=STANDARD_COLUMNS)


class MockMarketDataProvider:
    """In-memory market data for unit tests."""

    def __init__(self, ohlcv: pd.DataFrame | None = None) -> None:
        """Initialize with optional pre-built OHLCV data."""
        self._ohlcv = ohlcv or generate_trending_ohlcv()

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
        """Return synthetic OHLCV data."""
        return self._ohlcv.tail(limit).copy().reset_index(drop=True)

    def get_ticker(self, symbol: str) -> TickerSnapshot:
        """Return ticker based on latest synthetic close."""
        price = float(self._ohlcv.iloc[-1]["close"])
        return TickerSnapshot(symbol=symbol.upper(), price=price, timestamp=datetime.now(UTC))

    def get_derivatives(self, symbol: str) -> DerivativesSnapshot:
        """Return neutral derivatives snapshot."""
        return DerivativesSnapshot(
            symbol=symbol.upper(),
            funding_rate=0.0001,
            open_interest=1_000_000.0,
            mark_price=float(self._ohlcv.iloc[-1]["close"]),
        )
