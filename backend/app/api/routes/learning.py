"""Learning, similarity, and signal history endpoints."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.tracked import is_tracked
from app.core.service_dependencies import get_decision_pipeline, get_learning_engine
from app.engines.learning_engine import LearningEngine
from app.schemas.learning import (
    SignalRecordSchema,
    SimilarMatchSchema,
    SimilarityResponseSchema,
)
from app.services.decision_pipeline import DecisionPipelineService

router = APIRouter()


@router.get("/{symbol}/similarity", response_model=SimilarityResponseSchema)
async def get_asset_similarity(
    symbol: str,
    limit: int = Query(default=5, ge=1, le=20),
    pipeline: DecisionPipelineService = Depends(get_decision_pipeline),
    learning: LearningEngine = Depends(get_learning_engine),
) -> SimilarityResponseSchema:
    """Find historically similar evidence patterns for an asset."""
    normalized = symbol.upper()
    if not is_tracked(normalized):
        raise HTTPException(status_code=404, detail=f"Asset '{normalized}' is not tracked")

    decision = await asyncio.to_thread(pipeline.evaluate, normalized)
    await asyncio.to_thread(learning.record_decision, decision)

    matches = await asyncio.to_thread(
        learning.find_similar,
        normalized,
        decision.evidence,
        limit,
    )

    return SimilarityResponseSchema(
        symbol=normalized,
        matches=[
            SimilarMatchSchema(
                id=m.id,
                symbol=m.symbol,
                timestamp=m.timestamp,
                confidence=m.confidence,
                trade_grade=m.trade_grade,
                trade_state=m.trade_state,
                similarity=m.similarity,
                category_scores=m.category_scores,
            )
            for m in matches
        ],
        history_count=learning.store.count(normalized),
    )


@router.get("/{symbol}/signals", response_model=list[SignalRecordSchema])
async def get_asset_signals(
    symbol: str,
    limit: int = Query(default=20, ge=1, le=100),
    learning: LearningEngine = Depends(get_learning_engine),
) -> list[SignalRecordSchema]:
    """Return recent stored signal history for an asset."""
    normalized = symbol.upper()
    if not is_tracked(normalized):
        raise HTTPException(status_code=404, detail=f"Asset '{normalized}' is not tracked")

    records = await asyncio.to_thread(learning.recent_signals, normalized, limit)
    return [
        SignalRecordSchema(
            id=r.id,
            symbol=r.symbol,
            timestamp=r.timestamp,
            confidence=r.confidence,
            trade_grade=r.trade_grade,
            trade_state=r.trade_state,
            execution_signal=r.execution_signal,
            opportunity_score=r.opportunity_score,
            category_scores=r.category_scores,
        )
        for r in records
    ]
