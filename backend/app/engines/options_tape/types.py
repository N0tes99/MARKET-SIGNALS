"""Aggressive options tape types — hunt board, not orders."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from app.engines.opportunity_engine.equity_options.types import (
    ExecutionPlan,
    MomentumSnapshot,
    OptionCandidate,
)

DirectionBias = Literal["long", "short"]
Heat = Literal["hot", "warm"]


@dataclass
class TapeScreen:
    """Direction-agnostic tape snapshot used to pick long vs short."""

    symbol: str
    price: float
    ret_5d_pct: float
    ret_20d_pct: float
    dist_20dma_pct: float
    dist_50dma_pct: float
    relative_volume: float
    range_expansion: float
    atr_pct: float
    structure_score: float
    dist_20d_high_pct: float
    dist_20d_low_pct: float
    breakout_level: float
    support_level: float
    long_score: float
    short_score: float
    standout: bool
    factors: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


@dataclass
class OptionFlow:
    """Free Yahoo chain aggregates — not paid unusual-flow."""

    call_volume: int
    put_volume: int
    call_oi: int
    put_oi: int
    put_call_vol: float
    put_call_oi: float
    max_call_vol_oi: float
    max_put_vol_oi: float
    total_option_volume: int
    long_flow: float
    short_flow: float
    factors: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


@dataclass
class TapeHunt:
    """One aggressive long or short options hunt."""

    id: str
    symbol: str
    direction: DirectionBias
    heat: Heat
    hunt_score: float
    relative_volume: float
    range_expansion: float
    ret_5d_pct: float
    ret_20d_pct: float
    put_call_vol: float
    option_volume: int
    unusual_vol_oi: float
    factors: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    selected_option: OptionCandidate | None = None
    option_candidates: list[OptionCandidate] = field(default_factory=list)
    execution_plan: ExecutionPlan | None = None
    as_of: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class TapeBoard:
    """Balanced long/short hunt board."""

    longs: list[TapeHunt]
    shorts: list[TapeHunt]
    symbols_scanned: int
    symbols_optioned: int
    per_side: int
    scanned_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    note: str = (
        "Aggressive tape · equal long/short hunt · volume first · not orders"
    )


def screen_to_momentum(screen: TapeScreen) -> MomentumSnapshot:
    """Adapt tape screen into Layer 3 plan builder input."""
    return MomentumSnapshot(
        price=screen.price,
        ret_5d_pct=screen.ret_5d_pct,
        ret_20d_pct=screen.ret_20d_pct,
        dist_20dma_pct=screen.dist_20dma_pct,
        dist_50dma_pct=screen.dist_50dma_pct,
        relative_volume=screen.relative_volume,
        atr_pct=screen.atr_pct,
        structure_score=screen.structure_score,
        momentum_score=screen.long_score,
        breakout_level=screen.breakout_level,
        support_level=screen.support_level,
        factors=list(screen.factors),
        conflicts=list(screen.conflicts),
    )
