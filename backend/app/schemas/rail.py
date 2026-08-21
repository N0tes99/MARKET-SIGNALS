"""Surface 6 Rail API schemas — clerk-blind (no symbol / thesis / prices)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

VenueId = Literal["paper", "hyperliquid", "drift", "polymarket"]


class RailEnvelopeSchema(BaseModel):
    envelope_id: str
    venue: VenueId
    target_venue: VenueId
    market_kind: Literal["perp", "prediction", "outcome"]
    side: Literal["buy", "sell"]
    size_band: Literal["xs", "s", "m", "l"]
    urgency: Literal["passive", "normal", "aggressive"]
    edge_score: float
    ttl_seconds: int
    invalidation: str
    instrument_handle: str
    status: Literal["open", "closed"]
    created_at: datetime


class RailFillSchema(BaseModel):
    fill_id: str
    envelope_id: str
    venue: VenueId
    side: Literal["buy", "sell"]
    size_band: Literal["xs", "s", "m", "l"]
    status: Literal["paper_ack", "rejected"]
    latency_ms: int
    reason: str
    created_at: datetime


class RailVenueSchema(BaseModel):
    id: VenueId
    label: str
    chain: str
    market_kind: Literal["perp", "prediction", "outcome"]
    role: str
    status: Literal["ready", "planned", "refused"]
    note: str


class RailDeskSchema(BaseModel):
    as_of: datetime
    armed: bool
    live_enabled: bool
    phase: str
    default_venue: VenueId
    sitting_out: bool
    venues: list[RailVenueSchema] = Field(default_factory=list)
    envelopes: list[RailEnvelopeSchema] = Field(default_factory=list)
    fills: list[RailFillSchema] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RailSimulateRequest(BaseModel):
    envelope_id: str


class RailSimulateResponse(BaseModel):
    ok: bool
    fill: RailFillSchema | None = None
    detail: str | None = None
