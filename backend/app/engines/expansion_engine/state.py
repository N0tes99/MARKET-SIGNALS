"""Expansion state machine and directional scoring."""

from __future__ import annotations

from app.engines.expansion_engine.config import ExpansionConfig, default_expansion_config
from app.engines.expansion_engine.types import (
    CompressionResult,
    DirectionBias,
    ExpansionState,
    SqueezeFuelResult,
    TriggerResult,
)


def _confidence_label(net: float, trigger_active: bool) -> str:
    if net >= 85 and trigger_active:
        return "high"
    if net >= 70:
        return "medium"
    return "low"


def _setup_level(compression_score: float) -> str:
    if compression_score >= 85:
        return "high"
    if compression_score >= 75:
        return "medium"
    return "low"


def resolve_state(
    *,
    compression: CompressionResult | None,
    squeeze: SqueezeFuelResult,
    trigger: TriggerResult,
    mom_12h_pct: float | None,
    config: ExpansionConfig | None = None,
) -> ExpansionState:
    """DORMANT → PRIMED → TRIGGERING → EXPANDING."""
    cfg = config or default_expansion_config()
    comp = compression.score if compression else 0.0

    expanding = mom_12h_pct is not None and abs(mom_12h_pct) >= cfg.expanding_min_momentum_pct
    if expanding and trigger.active:
        return ExpansionState.EXPANDING
    if trigger.active and comp >= cfg.primed_min_compression - 10:
        return ExpansionState.TRIGGERING
    if comp >= cfg.primed_min_compression:
        return ExpansionState.PRIMED
    if comp >= 60 or squeeze.score >= 65:
        return ExpansionState.PRIMED
    return ExpansionState.DORMANT


def resolve_direction_bias(up: float, down: float, trigger: TriggerResult) -> DirectionBias:
    if trigger.active and trigger.direction in {"up", "down"}:
        return trigger.direction
    if up > down + 8:
        return "up"
    if down > up + 8:
        return "down"
    return "neutral"


def build_guidance(
    *,
    state: ExpansionState,
    direction: DirectionBias,
    trigger: TriggerResult,
) -> tuple[str, str, str]:
    """Horizon, invalidation, key trigger strings for UI."""
    if state in {ExpansionState.TRIGGERING, ExpansionState.EXPANDING}:
        horizon = "15m–4h"
    else:
        horizon = "1h–12h"
    if direction == "up":
        invalidation = "Failed breakout + negative CVD/volume fade"
        key = "Close above resistance with volume ≥1.5× baseline"
        if trigger.breakout_level:
            key = f"Hold above {trigger.breakout_level:.4g} with volume confirmation"
    elif direction == "down":
        invalidation = "Failed breakdown + buying absorption"
        key = "Close below support with volume ≥1.5× baseline"
        if trigger.breakout_level:
            key = f"Hold below {trigger.breakout_level:.4g} with volume confirmation"
    else:
        invalidation = "Compression resolves without directional break"
        key = "Wait for range break + volume on 15m"
    return horizon, invalidation, key


def confidence_from_scores(net: float, trigger_active: bool) -> str:
    return _confidence_label(net, trigger_active)


def setup_level_from_compression(compression: CompressionResult | None) -> str:
    return _setup_level(compression.score if compression else 0.0)
