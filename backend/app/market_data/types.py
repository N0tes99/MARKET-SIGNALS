"""Market data type definitions."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Candle:
    """Single OHLCV candle."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class TickerSnapshot:
    """Latest price snapshot for an asset."""

    symbol: str
    price: float
    timestamp: datetime
    market_cap: float | None = None


@dataclass(frozen=True)
class DerivativesSnapshot:
    """Derivatives market data from an exchange."""

    symbol: str
    funding_rate: float | None
    open_interest: float | None
    mark_price: float | None
