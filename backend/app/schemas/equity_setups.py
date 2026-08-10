"""Layer 3 equity-options setup API schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EquitySetupType = Literal["momentum_continuation", "breakout_convexity"]
DirectionBias = Literal["long", "short", "neutral"]
TradeStateHint = Literal["IGNORE", "WATCH"]
DataQuality = Literal["good", "degraded", "missing"]
OptionRight = Literal["call", "put"]


class StagedEntrySchema(BaseModel):
    """One scale-in step."""

    step: int
    label: str
    size_pct: float
    condition: str
    price_trigger: float | None = None


class ProfitZoneSchema(BaseModel):
    """Option-premium harvest rule."""

    option_gain_pct: float
    take_pct: float
    label: str


class ExecutionPlanSchema(BaseModel):
    """Staged smart-execution plan."""

    setup_name: str
    direction: DirectionBias
    max_risk_usd: float | None = None
    entries: list[StagedEntrySchema] = Field(default_factory=list)
    invalidation: list[str] = Field(default_factory=list)
    profit_zones: list[ProfitZoneSchema] = Field(default_factory=list)
    runner_pct: float = 30.0
    runner_rule: str = ""
    notes: str = ""


class OptionCandidateSchema(BaseModel):
    """Scored option contract."""

    underlying: str
    expiry: str
    strike: float
    right: OptionRight
    bid: float | None = None
    ask: float | None = None
    mid: float | None = None
    volume: int | None = None
    open_interest: int | None = None
    iv: float | None = None
    otm_pct: float = 0.0
    dte: int = 0
    convexity_score: float = 0.0
    liquidity_score: float = 0.0
    theta_score: float = 0.0
    iv_value_score: float = 0.0
    overall_score: float = 0.0
    rationale: str = ""


class EquityOptionsIdeaSchema(BaseModel):
    """Layer 3 setup idea — watch candidate with plan, not an order."""

    id: str
    symbol: str
    instrument_type: Literal["equity_option"] = "equity_option"
    setup_type: EquitySetupType
    direction_bias: DirectionBias
    confidence: float = Field(..., ge=0, le=100)
    opportunity_score: float = Field(..., ge=0, le=100)
    factors: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    trade_state_hint: TradeStateHint
    momentum_score: float = 0.0
    catalyst_score: float = 50.0
    liquidity_score: float = 50.0
    option_candidates: list[OptionCandidateSchema] = Field(default_factory=list)
    selected_option: OptionCandidateSchema | None = None
    execution_plan: ExecutionPlanSchema | None = None
    as_of: datetime
    data_quality: DataQuality = "good"


class AssetEquitySetupsResponse(BaseModel):
    """Layer 3 ideas for one asset."""

    symbol: str
    setups: list[EquityOptionsIdeaSchema] = Field(default_factory=list)
    scanned_at: datetime


class GlobalEquitySetupsResponse(BaseModel):
    """Cross-asset Layer 3 feed."""

    setups: list[EquityOptionsIdeaSchema] = Field(default_factory=list)
    scanned_at: datetime
    symbols_scanned: int = 0
    watch_only: bool = False
    min_confidence: float = 0.0
