"""Layer 3 equity-options opportunity types — watch candidates, not orders."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

EquitySetupType = Literal["momentum_continuation", "breakout_convexity"]
DirectionBias = Literal["long", "short", "neutral"]
TradeStateHint = Literal["IGNORE", "WATCH"]
DataQuality = Literal["good", "degraded", "missing"]
OptionRight = Literal["call", "put"]


@dataclass
class StagedEntry:
    """One scale-in step of a smart execution plan."""

    step: int
    label: str
    size_pct: float
    condition: str
    price_trigger: float | None = None


@dataclass
class ProfitZone:
    """Option-premium harvest rule (not underlying strike chase)."""

    option_gain_pct: float
    take_pct: float
    label: str


@dataclass
class ExecutionPlan:
    """Staged entries + invalidation + profit management."""

    setup_name: str
    direction: DirectionBias
    max_risk_usd: float | None
    entries: list[StagedEntry] = field(default_factory=list)
    invalidation: list[str] = field(default_factory=list)
    profit_zones: list[ProfitZone] = field(default_factory=list)
    runner_pct: float = 30.0
    runner_rule: str = ""
    notes: str = ""


@dataclass
class OptionCandidate:
    """Scored option contract candidate."""

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


@dataclass
class MomentumSnapshot:
    """Explainable momentum features for equity setups."""

    price: float
    ret_5d_pct: float
    ret_20d_pct: float
    dist_20dma_pct: float
    dist_50dma_pct: float
    relative_volume: float
    atr_pct: float
    structure_score: float
    momentum_score: float
    breakout_level: float | None
    support_level: float | None
    factors: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


@dataclass
class EquityOptionsIdea:
    """Layer 3 setup idea with option pick and staged plan.

    Confidence is evidence agreement, not an execution signal.
    MVP trade_state_hint is IGNORE or WATCH only — never EXECUTE.
    """

    id: str
    symbol: str
    setup_type: EquitySetupType
    direction_bias: DirectionBias
    confidence: float
    opportunity_score: float
    factors: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    trade_state_hint: TradeStateHint = "IGNORE"
    momentum_score: float = 0.0
    catalyst_score: float = 50.0
    liquidity_score: float = 50.0
    option_candidates: list[OptionCandidate] = field(default_factory=list)
    selected_option: OptionCandidate | None = None
    execution_plan: ExecutionPlan | None = None
    as_of: datetime = field(default_factory=lambda: datetime.now(UTC))
    data_quality: DataQuality = "good"
    instrument_type: Literal["equity_option"] = "equity_option"
