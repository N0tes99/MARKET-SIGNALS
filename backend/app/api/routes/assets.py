"""Asset dashboard endpoints."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.api.tracked import TRACKED_SYMBOLS, is_tracked
from app.core.service_dependencies import get_decision_pipeline, get_learning_engine
from app.engines.learning_engine import LearningEngine
from app.market_data.symbols import get_asset_class
from app.schemas.assets import AssetSummary
from app.services.decision_pipeline import DecisionPipelineService
from app.utils.ttl_cache import TTLCache

router = APIRouter()

_ASSETS_LIST_CACHE: TTLCache[list[AssetSummary]] = TTLCache(ttl_seconds=90.0)


def _score_for_category(decision, category: str) -> float:
    """Extract category score from decision evidence."""
    for item in decision.evidence.items:
        if item.category == category:
            return item.score
    return 0.0


def _trend_label(trend_score: float) -> str:
    """Map trend score to direction label."""
    if trend_score == 0.0:
        return "Neutral"
    if trend_score >= 60:
        return "Bullish"
    if trend_score <= 40:
        return "Bearish"
    return "Neutral"


def _build_summary(decision) -> AssetSummary:
    """Build dashboard summary from a pipeline decision."""
    trend_score = _score_for_category(decision, "Trend")
    return AssetSummary(
        symbol=decision.symbol,
        confidence=decision.evidence.total_confidence,
        trend=_trend_label(trend_score),
        trade_grade=decision.opportunity.trade_grade,
        buyer_strength=_score_for_category(decision, "Momentum"),
        risk=_score_for_category(decision, "Risk"),
        expected_value=decision.opportunity.expected_value,
        trade_state=decision.trade_state.value,
        execution_signal=decision.execution.signal.value,
        asset_class=get_asset_class(decision.symbol).value,
    )


def _record_decisions(learning: LearningEngine, decisions) -> None:
    """Store pipeline decisions for learning and similarity."""
    for decision in decisions:
        learning.record_decision(decision)


def _load_asset_summaries(
    pipeline: DecisionPipelineService,
    learning: LearningEngine,
) -> list[AssetSummary]:
    """Rank all tracked assets and build dashboard summaries."""
    decisions = pipeline.rank_all(list(TRACKED_SYMBOLS))
    _record_decisions(learning, decisions)
    return [_build_summary(d) for d in decisions]


@router.get("", response_model=list[AssetSummary])
async def list_assets(
    pipeline: DecisionPipelineService = Depends(get_decision_pipeline),
    learning: LearningEngine = Depends(get_learning_engine),
) -> list[AssetSummary]:
    """Return summary metrics for all tracked dashboard assets (cached ~90s)."""
    return await asyncio.to_thread(
        _ASSETS_LIST_CACHE.get_or_set,
        "dashboard",
        lambda: _load_asset_summaries(pipeline, learning),
    )


@router.get("/{symbol}", response_model=AssetSummary)
async def get_asset(
    symbol: str,
    pipeline: DecisionPipelineService = Depends(get_decision_pipeline),
) -> AssetSummary:
    """Return summary metrics for a single asset."""
    normalized = symbol.upper()
    if not is_tracked(normalized):
        raise HTTPException(status_code=404, detail=f"Asset '{normalized}' is not tracked")

    decision = await asyncio.to_thread(pipeline.evaluate, normalized)
    return _build_summary(decision)
