"""Crypto perps board schemas — funding, liquidations, idea activity."""

from datetime import datetime

from pydantic import BaseModel, Field


class PerpsFundingRowSchema(BaseModel):
    """Linear funding / OI snapshot for one symbol (Bybit or OKX)."""

    symbol: str
    funding_rate: float | None = None
    funding_bps: float | None = None
    funding_trend_bps: float | None = None
    open_interest: float | None = None
    oi_change_pct: float | None = None
    mark_price: float | None = None
    source: str = ""
    available: bool = False
    note: str = ""


class PerpsLiquidationRowSchema(BaseModel):
    """Aggregated long/short liquidations for one symbol."""

    symbol: str
    long_usd: float | None = None
    short_usd: float | None = None
    total_usd: float | None = None
    long_share: float | None = None
    interval: str = "4h"
    score: float | None = None
    description: str = ""
    available: bool = False
    coinglass_url: str | None = None


class PerpsIdeaRowSchema(BaseModel):
    """Layer-2 style perp idea already on the setups feed."""

    id: str
    symbol: str
    setup_type: str
    direction_bias: str
    confidence: float
    factors: list[str] = Field(default_factory=list)
    trade_state_hint: str = "IGNORE"


class PerpsBoardSchema(BaseModel):
    """Read-only crypto perps activity board."""

    as_of: datetime
    universe: list[str]
    funding: list[PerpsFundingRowSchema]
    liquidations: list[PerpsLiquidationRowSchema]
    ideas: list[PerpsIdeaRowSchema] = Field(default_factory=list)
    liquidations_configured: bool
    liquidations_note: str
    funding_source: str = "okx|bybit"
    symbols_scanned: int = 0
    funding_filled: int = 0
    liquidations_filled: int = 0
