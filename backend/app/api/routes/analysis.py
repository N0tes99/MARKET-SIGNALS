"""Analysis and AI explanation endpoints."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.tracked import is_tracked
from app.core.service_dependencies import get_ai_analyst, get_decision_pipeline
from app.engines.ai_engine import AIAnalyst
from app.engines.ai_engine.engine import AIExplanation
from app.engines.event_engine import EventEngine
from app.schemas.ai import AIExplanationSchema, AIExplanationVariantSchema
from app.services.decision_pipeline import DecisionPipelineService

router = APIRouter()


@router.get("/{symbol}/analysis", response_model=AIExplanationSchema)
async def get_asset_analysis(
    symbol: str,
    compare: bool = Query(
        False,
        description="Include both desk (local) and Groq readings when a key is set",
    ),
    pipeline: DecisionPipelineService = Depends(get_decision_pipeline),
    analyst: AIAnalyst = Depends(get_ai_analyst),
) -> AIExplanationSchema:
    """Return AI-generated explanation for an asset decision."""
    normalized = symbol.upper()
    if not is_tracked(normalized):
        raise HTTPException(status_code=404, detail=f"Asset '{normalized}' is not tracked")

    decision = await asyncio.to_thread(pipeline.evaluate, normalized)
    events = await asyncio.to_thread(
        EventEngine().snapshot, normalized, include_earnings=True
    )
    event_line = events.description if events.events else None

    if not compare:
        explanation = await asyncio.to_thread(analyst.explain_decision, decision)
        _prepend_event(explanation, event_line)
        return _to_schema(explanation)

    local, groq, groq_status = await asyncio.to_thread(
        analyst.explain_decision_pair, decision
    )
    _prepend_event(local, event_line)
    if groq is not None:
        _prepend_event(groq, event_line)
    primary = groq if groq is not None else local
    return _to_schema(
        primary,
        local=local,
        groq=groq,
        groq_status=groq_status,
    )


def _prepend_event(explanation: AIExplanation, event_line: str | None) -> None:
    if event_line:
        explanation.factors = [event_line, *explanation.factors]


def _variant(explanation: AIExplanation) -> AIExplanationVariantSchema:
    return AIExplanationVariantSchema(
        summary=explanation.summary,
        factors=explanation.factors,
        conflicts=explanation.conflicts,
        source=explanation.source,
        generated_at=explanation.generated_at,
    )


def _to_schema(
    explanation: AIExplanation,
    *,
    local: AIExplanation | None = None,
    groq: AIExplanation | None = None,
    groq_status: str | None = None,
) -> AIExplanationSchema:
    return AIExplanationSchema(
        symbol=explanation.symbol,
        summary=explanation.summary,
        confidence=explanation.confidence,
        factors=explanation.factors,
        conflicts=explanation.conflicts,
        source=explanation.source,
        generated_at=explanation.generated_at,
        local=_variant(local) if local is not None else None,
        groq=_variant(groq) if groq is not None else None,
        groq_status=groq_status,
    )
