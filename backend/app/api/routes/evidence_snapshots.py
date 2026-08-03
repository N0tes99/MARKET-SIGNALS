"""Evidence snapshot lookup endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.service_dependencies import get_evidence_service
from app.schemas.evidence import EvidenceBundleSchema
from app.services.evidence_service import EvidenceService

router = APIRouter()


@router.get("/snapshots/{snapshot_id}", response_model=EvidenceBundleSchema)
async def get_evidence_snapshot(
    snapshot_id: UUID,
    service: EvidenceService = Depends(get_evidence_service),
    session: AsyncSession = Depends(get_db),
) -> EvidenceBundleSchema:
    """Return a specific persisted evidence snapshot by ID."""
    snapshot = await service.get_by_id(session, snapshot_id)

    if snapshot is None:
        raise HTTPException(status_code=404, detail="Evidence snapshot not found")

    return snapshot
