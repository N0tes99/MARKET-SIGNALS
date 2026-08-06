"""Market quote schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class AssetQuote(BaseModel):
    """Latest price feed for a tracked asset."""

    symbol: str
    price: float | None = None
    change_pct: float | None = Field(
        default=None,
        description="Percent change vs prior close (approx session/24h)",
    )
    as_of: datetime | None = None
    available: bool = False


class CandlePoint(BaseModel):
    """Single OHLCV bar for mini charts."""

    t: datetime
    o: float
    h: float
    l: float
    c: float
    v: float


class CandleSeries(BaseModel):
    """OHLCV series for a symbol/timeframe."""

    symbol: str
    timeframe: str
    candles: list[CandlePoint] = Field(default_factory=list)
