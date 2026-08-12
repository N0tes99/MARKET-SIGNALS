"""Phase 1 stub dimension scorers — explicit missing-data placeholders.

Real fundamentals / catalysts / SI arrive in later phases. Structure stays
neutral here; Phase 2 wires existing momentum / Sector RS helpers.
"""

from __future__ import annotations

import logging

from app.engines.runner_engine.types import DimensionScore

logger = logging.getLogger(__name__)

_STUB_NOTE = "Phase 1 stub — awaiting dedicated provider"


def _neutral(name: str, *, extra: str | None = None) -> DimensionScore:
    factors = [_STUB_NOTE]
    if extra:
        factors.append(extra)
    score = DimensionScore(
        name=name,
        score=50.0,
        confidence=0.35,
        factors=factors,
        conflicts=["Insufficient data for high-conviction runner ranking"],
        data_quality="missing",
    )
    logger.info(
        "runner_dimension name=%s score=%.1f confidence=%.2f quality=%s",
        name,
        score.score,
        score.confidence,
        score.data_quality,
    )
    return score


def score_fundamental(symbol: str) -> DimensionScore:
    """Stub fundamental acceleration score."""
    return _neutral("fundamental", extra=f"{symbol}: no revenue/EPS acceleration series yet")


def score_catalyst(symbol: str) -> DimensionScore:
    """Stub catalyst score."""
    return _neutral("catalyst", extra=f"{symbol}: no catalyst detector wired yet")


def score_structure(symbol: str) -> DimensionScore:
    """Stub market-structure score (Phase 2: momentum + RS + volume)."""
    return _neutral(
        "structure",
        extra=f"{symbol}: structure will reuse Layer 3 momentum / Sector RS in Phase 2",
    )


def score_asymmetry(symbol: str) -> DimensionScore:
    """Stub asymmetry score (Phase 2: market cap / float / liquidity)."""
    return _neutral("asymmetry", extra=f"{symbol}: market-cap / dilution feeds pending")


def score_discovery_gap(symbol: str) -> DimensionScore:
    """Stub discovery-gap score (Phase 3)."""
    return _neutral(
        "discovery_gap",
        extra=f"{symbol}: needs fundamentals vs price expansion comparison",
    )


def score_theme_bottleneck(symbol: str) -> DimensionScore:
    """Stub theme / bottleneck score (Phase 3)."""
    return _neutral("theme_bottleneck", extra=f"{symbol}: theme graph not configured yet")


def score_institutional(symbol: str) -> DimensionScore:
    """Stub institutional accumulation (Phase 3)."""
    return _neutral("institutional_accum", extra=f"{symbol}: ownership change feed pending")


def score_short_squeeze(symbol: str) -> DimensionScore:
    """Stub short-squeeze accelerant (Phase 3) — never a thesis alone."""
    return _neutral(
        "short_squeeze_potential",
        extra=f"{symbol}: short interest is accelerant-only when fundamentals exist",
    )


def score_all_dimensions(symbol: str) -> dict[str, DimensionScore]:
    """Return all Phase 1 stub dimensions for a symbol."""
    return {
        "fundamental": score_fundamental(symbol),
        "catalyst": score_catalyst(symbol),
        "structure": score_structure(symbol),
        "asymmetry": score_asymmetry(symbol),
        "discovery_gap": score_discovery_gap(symbol),
        "theme_bottleneck": score_theme_bottleneck(symbol),
        "institutional_accum": score_institutional(symbol),
        "short_squeeze_potential": score_short_squeeze(symbol),
    }
