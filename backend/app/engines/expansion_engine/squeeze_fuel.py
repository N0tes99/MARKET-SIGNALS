"""Derivatives squeeze fuel — estimates forced buying/selling zones."""

from __future__ import annotations

from app.engines.expansion_engine.config import ExpansionConfig, default_expansion_config
from app.engines.expansion_engine.types import (
    CompressionResult,
    DirectionBias,
    SqueezeFuelLevel,
    SqueezeFuelResult,
)
from app.market_data.providers.bybit_derivatives import DerivativesDepth, oi_change_pct
from app.utils.scoring_helpers import clamp_score


def _fuel_label(score: float) -> str:
    if score >= 85:
        return "extreme"
    if score >= 70:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def analyze_squeeze_fuel(
    *,
    compression: CompressionResult | None,
    depth: DerivativesDepth | None,
    price: float | None,
    recent_momentum_pct: float | None,
    config: ExpansionConfig | None = None,
) -> SqueezeFuelResult:
    """Estimate squeeze fuel aligned WITH crowd when compression + OI/funding stack."""
    cfg = config or default_expansion_config()
    factors: list[str] = []
    conflicts: list[str] = []
    score = 45.0
    direction: DirectionBias = "neutral"

    funding_bps: float | None = None
    oi_delta: float | None = None
    if depth is not None and depth.funding_rate is not None:
        funding_bps = depth.funding_rate * 10_000
        oi_delta = oi_change_pct(depth.oi_history)

    comp_score = compression.score if compression else 50.0

    # Direction from recent momentum when available
    if recent_momentum_pct is not None:
        if recent_momentum_pct >= 0.3:
            direction = "up"
        elif recent_momentum_pct <= -0.3:
            direction = "down"

    if compression and compression.score >= cfg.compression_primedd_score:
        score += 18.0
        factors.append(f"Compression {compression.score:.0f} loads spring")
    elif compression and compression.score >= 60:
        score += 8.0

    if funding_bps is not None:
        factors.append(f"Funding {funding_bps:+.2f} bps")
        abs_bps = abs(funding_bps)
        if direction == "up" and funding_bps >= cfg.squeeze_funding_soft_bps:
            # Crowded longs + up move + compression = squeeze continuation fuel
            score += min(abs_bps, 20.0) * 0.8
            factors.append("Positive funding + upside — squeeze fuel WITH crowd")
        elif direction == "down" and funding_bps <= -cfg.squeeze_funding_soft_bps:
            score += min(abs_bps, 20.0) * 0.8
            factors.append("Negative funding + downside — short squeeze fuel")
        elif abs_bps >= cfg.squeeze_funding_extreme_bps and comp_score < 60:
            conflicts.append("Extreme funding without compression — chase risk")
            score -= 10.0

    if oi_delta is not None:
        factors.append(f"OI Δ {oi_delta:+.1f}%")
        if direction == "up":
            if oi_delta <= cfg.squeeze_oi_unwind_pct:
                score += 14.0
                factors.append("OI declining into strength — short covering")
            elif oi_delta >= cfg.squeeze_oi_build_pct and comp_score >= 70:
                score += 10.0
                factors.append("OI building under compression — fuel stacking")
        elif direction == "down" and oi_delta <= cfg.squeeze_oi_unwind_pct:
            score += 10.0
            factors.append("OI unwinding on weakness")

    if price is None or price <= 0:
        conflicts.append("Price unavailable — fuel map approximate")

    score = clamp_score(score)

    # Fuel map at +1% … +4% (upside default; mirror for down)
    levels: list[SqueezeFuelLevel] = []
    for pct in (1.0, 2.0, 3.0, 4.0):
        tier = clamp_score(score + pct * 4.0)
        levels.append(SqueezeFuelLevel(pct_move=pct, label=_fuel_label(tier)))

    if not factors:
        factors.append("Squeeze fuel neutral — awaiting compression + positioning")

    return SqueezeFuelResult(
        score=score,
        direction=direction,
        levels=levels,
        factors=factors,
        conflicts=conflicts,
    )
