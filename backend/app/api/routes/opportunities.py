"""Opportunity ranking endpoints."""

import asyncio

from fastapi import APIRouter, Depends

from app.api.tracked import TRACKED_SYMBOLS
from app.core.service_dependencies import get_decision_pipeline
from app.schemas.opportunities import OpportunitySummary
from app.services.decision_pipeline import DecisionPipelineService

router = APIRouter()


@router.get("", response_model=list[OpportunitySummary])
async def list_opportunities(
    pipeline: DecisionPipelineService = Depends(get_decision_pipeline),
) -> list[OpportunitySummary]:
    """Return ranked opportunities across all tracked assets."""
    decisions = await asyncio.to_thread(pipeline.rank_all, list(TRACKED_SYMBOLS))
    return [
        OpportunitySummary(
            symbol=d.symbol,
            opportunity_score=d.opportunity.opportunity_score,
            trade_grade=d.opportunity.trade_grade,
            expected_value=d.opportunity.expected_value,
            trade_state=d.trade_state.value,
        )
        for d in decisions
    ]
