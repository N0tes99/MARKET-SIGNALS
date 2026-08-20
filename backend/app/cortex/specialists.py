"""Specialist adapters — wrap existing engines as cortex contributors."""

from __future__ import annotations

import logging

from app.cortex.types import SpecialistOpinion
from app.engines.derivatives_engine.engine import DerivativesEngine
from app.engines.regime_engine.engine import MarketRegime, RegimeEngine
from app.market_data.service import MarketDataService

logger = logging.getLogger(__name__)


def _regime_direction(regime: MarketRegime) -> str | None:
    if regime == MarketRegime.TRENDING:
        return "neutral"
    if regime == MarketRegime.QUIET:
        return "neutral"
    return None


def collect_regime_opinion(
    engine: RegimeEngine,
    symbol: str,
    *,
    timeframe: str = "1h",
) -> SpecialistOpinion:
    try:
        result = engine.classify(symbol, timeframe=timeframe)
    except Exception:
        logger.exception("Cortex regime specialist failed for %s", symbol)
        return SpecialistOpinion(
            specialist="regime",
            score=None,
            direction=None,
            factors=[f"{symbol}: regime unavailable"],
        )

    score = 50.0
    if result.regime == MarketRegime.QUIET:
        score = 72.0
    elif result.regime == MarketRegime.TRENDING:
        score = 65.0
    elif result.regime == MarketRegime.VOLATILE:
        score = 42.0
    elif result.regime == MarketRegime.RANGING:
        score = 55.0

    return SpecialistOpinion(
        specialist="regime",
        score=round(score, 2),
        direction=_regime_direction(result.regime),
        factors=[result.description],
        metadata={
            "regime": result.regime.value,
            "confidence": result.confidence,
            "vix": result.vix,
        },
    )


def collect_derivatives_opinion(
    engine: DerivativesEngine,
    symbol: str,
) -> SpecialistOpinion:
    try:
        result = engine.analyze(symbol)
    except Exception:
        logger.exception("Cortex derivatives specialist failed for %s", symbol)
        return SpecialistOpinion(
            specialist="derivatives",
            score=None,
            direction=None,
            factors=[f"{symbol}: derivatives unavailable"],
        )

    if result is None:
        return SpecialistOpinion(
            specialist="derivatives",
            score=None,
            direction=None,
            factors=[f"{symbol}: derivatives unavailable"],
        )

    direction = None
    if result.funding_rate is not None:
        if result.funding_rate > 0.0003:
            direction = "up"
        elif result.funding_rate < -0.0003:
            direction = "down"

    return SpecialistOpinion(
        specialist="derivatives",
        score=round(result.score, 2),
        direction=direction,
        factors=[result.description],
        metadata={
            "funding_rate": result.funding_rate,
            "open_interest": result.open_interest,
            "source": result.source,
        },
    )


def build_specialist_engines(
    market: MarketDataService,
) -> tuple[RegimeEngine, DerivativesEngine]:
    return RegimeEngine(market), DerivativesEngine(market)
