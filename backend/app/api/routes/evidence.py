"""Evidence endpoints for asset-specific accumulation."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tracked import is_tracked
from app.core.dependencies import get_db
from app.core.service_dependencies import get_evidence_service
from app.schemas.evidence import EvidenceBundleSchema
from app.services.evidence_service import EvidenceService

router = APIRouter()


def _validate_symbol(symbol: str) -> str:
    """Normalize and validate a tracked asset symbol."""
    normalized = symbol.upper()
    if not is_tracked(normalized):
        raise HTTPException(status_code=404, detail=f"Asset '{normalized}' is not tracked")
    return normalized


@router.get("/{symbol}/evidence", response_model=EvidenceBundleSchema)
async def get_asset_evidence(
    symbol: str,
    timeframe: str = Query(default="1h", description="Analysis timeframe"),
    persist: bool = Query(default=False, description="Persist snapshot to database"),
    service: EvidenceService = Depends(get_evidence_service),
    session: AsyncSession = Depends(get_db),
) -> EvidenceBundleSchema:
    """Return accumulated evidence for an asset.

    Computes evidence on-the-fly from all registered engines.
    Set ``persist=true`` to store an immutable snapshot.
    """
    normalized = _validate_symbol(symbol)

    if persist:
        return await service.accumulate_and_persist(session, normalized, timeframe)

    return await asyncio.to_thread(service.accumulate, normalized, timeframe)


@router.post("/{symbol}/evidence", response_model=EvidenceBundleSchema)
async def accumulate_and_persist_evidence(
    symbol: str,
    timeframe: str = Query(default="1h", description="Analysis timeframe"),
    service: EvidenceService = Depends(get_evidence_service),
    session: AsyncSession = Depends(get_db),
) -> EvidenceBundleSchema:
    """Accumulate evidence and persist an immutable snapshot."""
    normalized = _validate_symbol(symbol)
    return await service.accumulate_and_persist(session, normalized, timeframe)


@router.get("/{symbol}/evidence/latest", response_model=EvidenceBundleSchema)
async def get_latest_evidence(
    symbol: str,
    timeframe: str = Query(default="1h", description="Analysis timeframe"),
    service: EvidenceService = Depends(get_evidence_service),
    session: AsyncSession = Depends(get_db),
) -> EvidenceBundleSchema:
    """Return the most recently persisted evidence snapshot."""
    normalized = _validate_symbol(symbol)
    snapshot = await service.get_latest(session, normalized, timeframe)

    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail=f"No persisted evidence found for {normalized} ({timeframe})",
        )

    return snapshot
