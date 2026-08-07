"""Learning, similarity, signal history, and outcome endpoints."""

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.tracked import is_tracked
from app.core.auth_deps import get_current_user
from app.core.service_dependencies import get_decision_pipeline, get_learning_engine
from app.engines.learning_engine import LearningEngine
from app.engines.learning_engine.types import SignalOutcome, SignalRecord
from app.models.user import User
from app.schemas.learning import (
    OutcomeStatsSchema,
    OutcomeUpdateSchema,
    SignalRecordSchema,
    SimilarityResponseSchema,
    SimilarMatchSchema,
)
from app.services.decision_pipeline import DecisionPipelineService

router = APIRouter()


def _to_schema(record: SignalRecord) -> SignalRecordSchema:
    return SignalRecordSchema(
        id=record.id,
        symbol=record.symbol,
        timestamp=record.timestamp,
        confidence=record.confidence,
        trade_grade=record.trade_grade,
        trade_state=record.trade_state,
        execution_signal=record.execution_signal,
        opportunity_score=record.opportunity_score,
        category_scores=record.category_scores,
        expected_value=record.expected_value,
        entry_price=record.entry_price,
        stop_loss=record.stop_loss,
        take_profit=record.take_profit,
        outcome=record.outcome,
        realized_return_pct=record.realized_return_pct,
        notes=record.notes,
        resolved_at=record.resolved_at,
    )


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
                outcome=m.outcome,
                realized_return_pct=m.realized_return_pct,
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
    _user: User = Depends(get_current_user),
) -> list[SignalRecordSchema]:
    """Return recent signal history (private — signed-in only)."""
    normalized = symbol.upper()
    if not is_tracked(normalized):
        raise HTTPException(status_code=404, detail=f"Asset '{normalized}' is not tracked")

    records = await asyncio.to_thread(learning.recent_signals, normalized, limit)
    return [_to_schema(r) for r in records]


@router.post("/{symbol}/signals/log", response_model=SignalRecordSchema)
async def log_current_signal(
    symbol: str,
    pipeline: DecisionPipelineService = Depends(get_decision_pipeline),
    learning: LearningEngine = Depends(get_learning_engine),
    _user: User = Depends(get_current_user),
) -> SignalRecordSchema:
    """Evaluate the asset now and explicitly log it for outcome tracking."""
    normalized = symbol.upper()
    if not is_tracked(normalized):
        raise HTTPException(status_code=404, detail=f"Asset '{normalized}' is not tracked")

    decision = await asyncio.to_thread(pipeline.evaluate, normalized)
    record = await asyncio.to_thread(learning.record_decision, decision)
    return _to_schema(record)


@router.patch("/{symbol}/signals/{record_id}/outcome", response_model=SignalRecordSchema)
async def update_signal_outcome(
    symbol: str,
    record_id: UUID,
    body: OutcomeUpdateSchema,
    learning: LearningEngine = Depends(get_learning_engine),
    _user: User = Depends(get_current_user),
) -> SignalRecordSchema:
    """Record a realized win/loss/breakeven/no_trade outcome for a signal."""
    normalized = symbol.upper()
    if not is_tracked(normalized):
        raise HTTPException(status_code=404, detail=f"Asset '{normalized}' is not tracked")

    existing = learning.store.get(record_id)
    if existing is None or existing.symbol != normalized:
        raise HTTPException(
            status_code=404,
            detail=f"Signal '{record_id}' not found for {normalized}",
        )

    try:
        record = await asyncio.to_thread(
            learning.record_outcome,
            record_id,
            SignalOutcome(body.outcome),
            body.realized_return_pct,
            body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _to_schema(record)


@router.get("/{symbol}/outcomes/stats", response_model=OutcomeStatsSchema)
async def get_outcome_stats(
    symbol: str,
    learning: LearningEngine = Depends(get_learning_engine),
    _user: User = Depends(get_current_user),
) -> OutcomeStatsSchema:
    """Return win/loss stats for logged outcomes (private — signed-in only)."""
    normalized = symbol.upper()
    if not is_tracked(normalized):
        raise HTTPException(status_code=404, detail=f"Asset '{normalized}' is not tracked")

    stats = await asyncio.to_thread(learning.outcome_stats, normalized)
    return OutcomeStatsSchema(symbol=normalized, **stats)
