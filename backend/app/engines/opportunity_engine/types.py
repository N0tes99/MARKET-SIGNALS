"""Opportunity setup idea types — watch candidates, not trade orders."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

SetupType = Literal["funding_extreme", "liq_flush", "basis_rich"]
DirectionBias = Literal["long", "short", "neutral", "relative"]
TradeStateHint = Literal["IGNORE", "WATCH"]
InstrumentType = Literal["perp"]
DataQuality = Literal["good", "degraded", "missing"]


class SetupTypeEnum(StrEnum):
    """Known setup scanners."""

    FUNDING_EXTREME = "funding_extreme"
    LIQ_FLUSH = "liq_flush"
    BASIS_RICH = "basis_rich"


@dataclass
class OpportunityIdea:
    """A setup candidate / watch idea with evidence factors and conflicts.

    Confidence is evidence agreement, not an execution signal.
    MVP trade_state_hint is IGNORE or WATCH only — never EXECUTE.
    """

    id: str
    symbol: str
    instrument_type: InstrumentType
    setup_type: SetupType
    direction_bias: DirectionBias
    confidence: float
    factors: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    trade_state_hint: TradeStateHint = "IGNORE"
    as_of: datetime = field(default_factory=lambda: datetime.now(UTC))
    data_quality: DataQuality = "good"
