"""Opportunity setup idea API schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SetupType = Literal["funding_extreme", "liq_flush", "basis_rich"]
DirectionBias = Literal["long", "short", "neutral", "relative"]
TradeStateHint = Literal["IGNORE", "WATCH"]
DataQuality = Literal["good", "degraded", "missing"]


class OpportunityIdeaSchema(BaseModel):
    """Setup candidate / watch idea — evidence surface, not an order."""

    id: str
    symbol: str
    instrument_type: Literal["perp"] = "perp"
    setup_type: SetupType
    direction_bias: DirectionBias
    confidence: float = Field(..., ge=0, le=100, description="Evidence agreement 0–100")
    factors: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    trade_state_hint: TradeStateHint = Field(
        ...,
        description="MVP: IGNORE or WATCH only — never EXECUTE",
    )
    as_of: datetime
    data_quality: DataQuality = "good"


class AssetSetupsResponse(BaseModel):
    """Setup ideas for a single asset."""

    symbol: str
    setups: list[OpportunityIdeaSchema] = Field(default_factory=list)
    scanned_at: datetime


class GlobalSetupsResponse(BaseModel):
    """Cross-asset setup feed for the dashboard."""

    setups: list[OpportunityIdeaSchema] = Field(default_factory=list)
    scanned_at: datetime
    symbols_scanned: int = 0
    watch_only: bool = False
    min_confidence: float = 0.0
