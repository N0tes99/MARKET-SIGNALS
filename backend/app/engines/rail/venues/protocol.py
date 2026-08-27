"""Venue adapter protocol. Execution only — no engine imports."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.engines.rail.types import ClerkFill, OpportunityEnvelope, SealedInstrument, VenueId


class LiveVenueDisabled(Exception):
    """Phase A (and unarmed later phases) must not place live orders."""

    def __init__(self, venue: VenueId, detail: str) -> None:
        self.venue = venue
        self.detail = detail
        super().__init__(detail)


@runtime_checkable
class VenueAdapter(Protocol):
    venue_id: VenueId

    def submit(
        self,
        envelope: OpportunityEnvelope,
        sealed: SealedInstrument,
    ) -> ClerkFill:
        """Attempt a fill. Live adapters must refuse in Phase A/B."""
        ...
