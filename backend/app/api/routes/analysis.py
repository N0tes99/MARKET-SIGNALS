"""Analysis and AI explanation endpoints."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.api.tracked import is_tracked
from app.core.service_dependencies import get_ai_analyst, get_decision_pipeline
from app.engines.ai_engine import AIAnalyst
from app.schemas.ai import AIExplanationSchema
from app.services.decision_pipeline import DecisionPipelineService

router = APIRouter()


@router.get("/{symbol}/analysis", response_model=AIExplanationSchema)
async def get_asset_analysis(
    symbol: str,
    pipeline: DecisionPipelineService = Depends(get_decision_pipeline),
    analyst: AIAnalyst = Depends(get_ai_analyst),
) -> AIExplanationSchema:
    """Return AI-generated explanation for an asset decision."""
    normalized = symbol.upper()
    if not is_tracked(normalized):
        raise HTTPException(status_code=404, detail=f"Asset '{normalized}' is not tracked")

    decision = await asyncio.to_thread(pipeline.evaluate, normalized)
    explanation = await asyncio.to_thread(analyst.explain_decision, decision)

    return AIExplanationSchema(
        symbol=explanation.symbol,
        summary=explanation.summary,
        confidence=explanation.confidence,
        factors=explanation.factors,
        conflicts=explanation.conflicts,
        source=explanation.source,
        generated_at=explanation.generated_at,
    )
