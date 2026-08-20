"""Expansion engine data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Literal

DirectionBias = Literal["up", "down", "neutral"]


class ExpansionState(StrEnum):
    """Market expansion lifecycle (MVP — four states)."""

    DORMANT = "dormant"
    PRIMED = "primed"
    TRIGGERING = "triggering"
    EXPANDING = "expanding"


@dataclass(frozen=True)
class ScoreContributor:
    """One decomposed score line for explainability."""

    label: str
    points: float
    detail: str = ""


@dataclass(frozen=True)
class CompressionResult:
    """Volatility / range compression reading."""

    score: float
    atr_percentile: float | None
    bb_width_percentile: float | None
    range_compression_pct: float | None
    volume_compression_pct: float | None
    factors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SqueezeFuelLevel:
    """Estimated liquidation fuel at a price offset."""

    pct_move: float
    label: str  # low | medium | high | extreme


@dataclass(frozen=True)
class SqueezeFuelResult:
    """Short/long squeeze fuel estimate."""

    score: float
    direction: DirectionBias
    levels: list[SqueezeFuelLevel] = field(default_factory=list)
    factors: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TriggerResult:
    """Breakout + volume confirmation on lower timeframe."""

    active: bool
    direction: DirectionBias
    volume_ratio: float | None
    breakout_level: float | None
    factors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExpansionCandidate:
    """One symbol expansion radar reading."""

    id: str
    symbol: str
    state: ExpansionState
    direction_bias: DirectionBias
    up_score: float
    down_score: float
    net_score: float
    confidence: Literal["low", "medium", "high"]
    setup_level: Literal["low", "medium", "high"]
    trigger_active: bool
    horizon: str
    invalidation: str
    key_trigger: str
    compression: CompressionResult
    squeeze: SqueezeFuelResult
    trigger: TriggerResult
    contributors: list[ScoreContributor] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    factors: list[str] = field(default_factory=list)
    price: float | None = None
    funding_bps: float | None = None
    oi_change_pct: float | None = None
    mom_12h_pct: float | None = None
    as_of: datetime | None = None
