"""Specialist adapters — wrap existing engines as cortex contributors."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.cortex.types import SpecialistOpinion
from app.engines.buyer_seller_engine.engine import BuyerSellerEngine
from app.engines.derivatives_engine.engine import DerivativesEngine
from app.engines.event_engine.engine import EventEngine
from app.engines.macro_engine.engine import MacroEngine
from app.engines.regime_engine.engine import MarketRegime, RegimeEngine
from app.market_data.service import MarketDataService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SpecialistBundle:
    """Engines the cortex tick consults."""

    regime: RegimeEngine
    derivatives: DerivativesEngine
    cvd: BuyerSellerEngine
    news: EventEngine
    macro: MacroEngine


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


def collect_cvd_opinion(engine: BuyerSellerEngine, symbol: str) -> SpecialistOpinion:
    """Prefer public-trade CVD; fall back to the OHLCV buying-pressure proxy."""
    from app.market_data.tape import fetch_tape_cvd

    tape = fetch_tape_cvd(symbol)
    if tape is not None:
        return SpecialistOpinion(
            specialist="cvd",
            score=round(tape.score, 2),
            direction=tape.direction,
            factors=[
                f"{symbol}: tape CVD {tape.source} Δ={tape.delta:.0f} "
                f"n={tape.trade_count}",
            ],
            metadata={
                "buyer_strength": tape.score,
                "seller_strength": round(100.0 - tape.score, 2),
                "delta": tape.delta,
                "trade_count": tape.trade_count,
                "source": tape.source,
                "proxy": False,
            },
        )

    try:
        result = engine.analyze(symbol, timeframe="1h")
    except Exception:
        logger.exception("Cortex CVD specialist failed for %s", symbol)
        return SpecialistOpinion(
            specialist="cvd",
            score=None,
            direction=None,
            factors=[f"{symbol}: order-flow proxy unavailable"],
        )
    if result is None:
        return SpecialistOpinion(
            specialist="cvd",
            score=None,
            direction=None,
            factors=[f"{symbol}: order-flow proxy unavailable"],
        )

    direction = None
    if result.buyer_strength >= 58:
        direction = "up"
    elif result.seller_strength >= 58:
        direction = "down"

    return SpecialistOpinion(
        specialist="cvd",
        score=round(result.buyer_strength, 2),
        direction=direction,
        factors=[
            result.description,
            "CVD here is an OHLCV buying-pressure proxy, not exchange tape delta",
        ],
        metadata={
            "buyer_strength": result.buyer_strength,
            "seller_strength": result.seller_strength,
            "absorption": result.absorption,
            "volume_ratio": result.volume_ratio,
            "proxy": True,
        },
    )


def collect_news_opinion(engine: EventEngine, symbol: str) -> SpecialistOpinion:
    """Macro calendar / catalyst timing (FRED when keyed; not a headline NLP feed)."""
    try:
        snap = engine.snapshot(symbol, include_earnings=False)
    except Exception:
        logger.exception("Cortex news specialist failed for %s", symbol)
        return SpecialistOpinion(
            specialist="news",
            score=None,
            direction=None,
            factors=[f"{symbol}: event calendar unavailable"],
        )

    conflicts: list[str] = []
    if snap.nearest_days is not None and snap.nearest_days <= 1:
        conflicts.append("Imminent macro event — expansion trigger is higher-risk")

    return SpecialistOpinion(
        specialist="news",
        score=round(snap.score, 2),
        direction=None,
        factors=[snap.description, *list(snap.events[:3])],
        conflicts=conflicts,
        metadata={
            "nearest_days": snap.nearest_days,
            "events": list(snap.events[:6]),
        },
    )


def collect_macro_opinion(engine: MacroEngine) -> SpecialistOpinion:
    """Global DXY / rates context — one opinion per tick."""
    try:
        snap = engine.snapshot()
    except Exception:
        logger.exception("Cortex macro specialist failed")
        return SpecialistOpinion(
            specialist="macro",
            score=None,
            direction=None,
            factors=["Macro snapshot unavailable"],
        )

    direction = None
    if snap.score >= 55:
        direction = "up"
    elif snap.score <= 45:
        direction = "down"

    return SpecialistOpinion(
        specialist="macro",
        score=round(snap.score, 2),
        direction=direction,
        factors=[snap.description],
        metadata={
            "dxy": snap.dxy,
            "treasury_10y": snap.treasury_10y,
            "fed_funds_rate": snap.fed_funds_rate,
        },
    )


def build_specialist_engines(market: MarketDataService) -> SpecialistBundle:
    return SpecialistBundle(
        regime=RegimeEngine(market),
        derivatives=DerivativesEngine(market),
        cvd=BuyerSellerEngine(market),
        news=EventEngine(),
        macro=MacroEngine(),
    )
