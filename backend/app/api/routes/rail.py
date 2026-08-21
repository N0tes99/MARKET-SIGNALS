"""Surface 6 Rail — nested clerk API. Blind envelopes only."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.service_dependencies import get_rail_desk
from app.engines.rail.desk import RailDesk
from app.engines.rail.types import ClerkFill, OpportunityEnvelope, RailDeskSnapshot, VenueInfo
from app.schemas.rail import (
    RailDeskSchema,
    RailEnvelopeSchema,
    RailFillSchema,
    RailSimulateRequest,
    RailSimulateResponse,
    RailVenueSchema,
)

router = APIRouter()


def _envelope_schema(item: OpportunityEnvelope) -> RailEnvelopeSchema:
    return RailEnvelopeSchema(
        envelope_id=item.envelope_id,
        venue=item.venue,
        target_venue=item.target_venue,
        market_kind=item.market_kind,
        side=item.side,
        size_band=item.size_band,
        urgency=item.urgency,
        edge_score=round(float(item.edge_score), 2),
        ttl_seconds=int(item.ttl_seconds),
        invalidation=item.invalidation,
        instrument_handle=item.instrument_handle,
        status=item.status,
        created_at=item.created_at,
    )


def _fill_schema(item: ClerkFill) -> RailFillSchema:
    return RailFillSchema(
        fill_id=item.fill_id,
        envelope_id=item.envelope_id,
        venue=item.venue,
        side=item.side,
        size_band=item.size_band,
        status=item.status,
        latency_ms=item.latency_ms,
        reason=item.reason,
        created_at=item.created_at,
    )


def _venue_schema(item: VenueInfo) -> RailVenueSchema:
    return RailVenueSchema(
        id=item.id,
        label=item.label,
        chain=item.chain,
        market_kind=item.market_kind,
        role=item.role,
        status=item.status,
        note=item.note,
    )


def _desk_schema(snap: RailDeskSnapshot) -> RailDeskSchema:
    return RailDeskSchema(
        as_of=snap.as_of,
        armed=snap.armed,
        live_enabled=snap.live_enabled,
        phase=snap.phase,
        default_venue=snap.default_venue,
        sitting_out=snap.sitting_out,
        venues=[_venue_schema(v) for v in snap.venues],
        envelopes=[_envelope_schema(e) for e in snap.envelopes],
        fills=[_fill_schema(f) for f in snap.fills],
        notes=list(snap.notes),
    )


@router.get("/desk", response_model=RailDeskSchema)
def rail_desk(desk: RailDesk = Depends(get_rail_desk)) -> RailDeskSchema:
    """Blind clerk snapshot. Does not tick the paper agent."""
    return _desk_schema(desk.snapshot())


@router.post("/clerk/simulate", response_model=RailSimulateResponse)
def rail_simulate(
    body: RailSimulateRequest,
    desk: RailDesk = Depends(get_rail_desk),
) -> RailSimulateResponse:
    """Paper-venue dry-run. Never hits Hyperliquid, Drift, or Polymarket."""
    envelope_id = body.envelope_id.strip()
    if not envelope_id:
        raise HTTPException(status_code=400, detail="envelope_id is required")
    envelope, fill = desk.simulate(envelope_id)
    if envelope is None or fill is None:
        return RailSimulateResponse(ok=False, detail="unknown envelope")
    return RailSimulateResponse(ok=True, fill=_fill_schema(fill))
