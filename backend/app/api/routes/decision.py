"""Full decision pipeline endpoints."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.api.tracked import is_tracked
from app.core.service_dependencies import get_decision_pipeline
from app.schemas.decision import DecisionSchema
from app.services.decision_mapper import decision_to_schema
from app.services.decision_pipeline import DecisionPipelineService

router = APIRouter()


@router.get("/{symbol}/decision", response_model=DecisionSchema)
async def get_asset_decision(
    symbol: str,
    pipeline: DecisionPipelineService = Depends(get_decision_pipeline),
) -> DecisionSchema:
    """Return the full decision pipeline output for an asset."""
    normalized = symbol.upper()
    if not is_tracked(normalized):
        raise HTTPException(status_code=404, detail=f"Asset '{normalized}' is not tracked")

    result = await asyncio.to_thread(pipeline.evaluate, normalized)
    return decision_to_schema(result)
