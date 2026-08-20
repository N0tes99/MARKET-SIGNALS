"""Expansion state machine and directional scoring."""

from __future__ import annotations

from app.engines.expansion_engine.config import ExpansionConfig, default_expansion_config
from app.engines.expansion_engine.types import (
    CompressionResult,
    DirectionBias,
    ExpansionState,
    ScoreContributor,
    SqueezeFuelResult,
    TriggerResult,
)
from app.utils.scoring_helpers import clamp_score


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


def compose_scores(
    *,
    compression: CompressionResult | None,
    squeeze: SqueezeFuelResult,
    trigger: TriggerResult,
    mom_12h_pct: float | None,
    funding_bps: float | None,
    state: ExpansionState,
    config: ExpansionConfig | None = None,
) -> tuple[float, float, list[ScoreContributor], list[str]]:
    """Return (up_score, down_score, contributors, conflicts)."""
    cfg = config or default_expansion_config()
    contributors: list[ScoreContributor] = []
    conflicts: list[str] = list(squeeze.conflicts)

    comp_score = compression.score if compression else 50.0
    contributors.append(ScoreContributor("Compression", comp_score * cfg.weight_compression, ""))

    up = comp_score * cfg.weight_compression
    down = comp_score * cfg.weight_compression

    sq = squeeze.score
    if squeeze.direction == "up":
        up += sq * cfg.weight_squeeze
        contributors.append(ScoreContributor("Squeeze fuel", sq * cfg.weight_squeeze, "upside"))
    elif squeeze.direction == "down":
        down += sq * cfg.weight_squeeze
        contributors.append(ScoreContributor("Squeeze fuel", sq * cfg.weight_squeeze, "downside"))
    else:
        up += sq * cfg.weight_squeeze * 0.5
        down += sq * cfg.weight_squeeze * 0.5

    if trigger.active:
        trig_pts = 80.0 * cfg.weight_trigger
        if trigger.direction == "up":
            up += trig_pts
            contributors.append(ScoreContributor("Trigger", trig_pts, "breakout up"))
        elif trigger.direction == "down":
            down += trig_pts
            contributors.append(ScoreContributor("Trigger", trig_pts, "breakout down"))
    else:
        conflicts.append("No active breakout trigger")

    if mom_12h_pct is not None:
        mom_pts = min(abs(mom_12h_pct), 12.0) * cfg.weight_momentum * 3.0
        if mom_12h_pct > 0:
            up += mom_pts
            contributors.append(ScoreContributor("Momentum 12h", mom_pts, f"{mom_12h_pct:+.1f}%"))
        elif mom_12h_pct < 0:
            down += mom_pts
            contributors.append(ScoreContributor("Momentum 12h", mom_pts, f"{mom_12h_pct:+.1f}%"))

    if funding_bps is not None:
        deriv_pts = cfg.weight_derivatives * 50.0
        if funding_bps >= cfg.squeeze_funding_soft_bps:
            up += deriv_pts * 0.6
            contributors.append(
                ScoreContributor("Derivatives", deriv_pts * 0.6, "funding supports up")
            )
        elif funding_bps <= -cfg.squeeze_funding_soft_bps:
            down += deriv_pts * 0.6
            contributors.append(
                ScoreContributor("Derivatives", deriv_pts * 0.6, "funding supports down")
            )

    if state == ExpansionState.PRIMED:
        up = clamp_score(up + 5.0)
        down = clamp_score(down + 5.0)
    elif state == ExpansionState.TRIGGERING:
        up = clamp_score(up + 10.0)
        down = clamp_score(down + 10.0)
    elif state == ExpansionState.EXPANDING:
        up = clamp_score(up + 15.0)
        down = clamp_score(down + 15.0)

    return clamp_score(up), clamp_score(down), contributors, conflicts


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
