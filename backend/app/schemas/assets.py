"""Asset-related response schemas."""

from pydantic import BaseModel, Field


class AssetSummary(BaseModel):
    """Summary view of a tracked asset for the dashboard."""

    symbol: str = Field(..., description="Asset ticker symbol")
    confidence: float = Field(..., ge=0, le=100, description="Overall confidence score")
    trend: str = Field(..., description="Trend direction: Bullish, Neutral, or Bearish")
    trade_grade: str = Field(..., description="Letter grade for trade quality")
    buyer_strength: float = Field(..., ge=0, le=100, description="Buyer strength score")
    risk: float = Field(..., ge=0, le=100, description="Risk score")
    expected_value: float = Field(..., description="Expected value of the opportunity")
    trade_state: str = Field(
        default="IGNORE",
        description="Current trade state: IGNORE, WATCH, EXECUTE, MANAGE, or EXIT",
    )
    execution_signal: str = Field(
        default="WAIT",
        description="Entry timing signal: WAIT, WATCH, or EXECUTE",
    )
    asset_class: str = Field(
        default="crypto",
        description="Asset category: crypto, stock, or etf",
    )
    data_degraded: bool = Field(
        default=False,
        description="True when market data is stale or providers are failing",
    )
    data_age_seconds: float | None = Field(
        default=None,
        description="Seconds since last successful OHLCV/ticker fetch, if known",
    )
    data_stale_reason: str | None = Field(
        default=None,
        description="stale_data | provider_errors when degraded",
    )
