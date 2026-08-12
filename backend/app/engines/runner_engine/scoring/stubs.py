"""Phase 2: real structure/asymmetry; other dimensions stay missing stubs."""

from __future__ import annotations

import logging

from app.engines.runner_engine.config import RunnerConfig, default_runner_config
from app.engines.runner_engine.scoring.asymmetry import score_asymmetry
from app.engines.runner_engine.scoring.structure import score_structure
from app.engines.runner_engine.types import DimensionScore, RunnerTapeSnapshot
from app.market_data.service import MarketDataService

logger = logging.getLogger(__name__)

_STUB_NOTE = "Phase 2 stub — awaiting dedicated provider"


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


def score_all_dimensions(
    symbol: str,
    *,
    market_data: MarketDataService | None = None,
    config: RunnerConfig | None = None,
) -> tuple[dict[str, DimensionScore], RunnerTapeSnapshot]:
    """Return Phase 2 dimensions: live structure/asymmetry, stub remainder."""
    normalized = symbol.upper().strip()
    md = market_data or MarketDataService()
    cfg = config or default_runner_config()
    structure, tape = score_structure(normalized, market_data=md)
    return (
        {
            "fundamental": score_fundamental(normalized),
            "catalyst": score_catalyst(normalized),
            "structure": structure,
            "asymmetry": score_asymmetry(normalized, market_data=md, config=cfg),
            "discovery_gap": score_discovery_gap(normalized),
            "theme_bottleneck": score_theme_bottleneck(normalized),
            "institutional_accum": score_institutional(normalized),
            "short_squeeze_potential": score_short_squeeze(normalized),
        },
        tape,
    )
