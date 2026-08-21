"""Paper venue — dry-run ack only. Does not open a second paper trade."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.engines.rail.types import ClerkFill, OpportunityEnvelope, SealedInstrument
from app.engines.rail.venues.protocol import VenueAdapter

PAPER_ACK_REASON = (
    "Phase A dry-run: clerk would send this to the venue without reading the desk. "
    "No live order. No second paper fill."
)


class PaperVenue(VenueAdapter):
    venue_id = "paper"

    def submit(
        self,
        envelope: OpportunityEnvelope,
        sealed: SealedInstrument,
    ) -> ClerkFill:
        del sealed  # paper ack is blind; resolution is only for live adapters later
        if envelope.status != "open":
            return ClerkFill(
                fill_id=str(uuid4()),
                envelope_id=envelope.envelope_id,
                venue="paper",
                side=envelope.side,
                size_band=envelope.size_band,
                status="rejected",
                latency_ms=0,
                reason="envelope is closed; clerk sits out",
                created_at=datetime.now(UTC),
            )
        if envelope.venue != "paper":
            return ClerkFill(
                fill_id=str(uuid4()),
                envelope_id=envelope.envelope_id,
                venue="paper",
                side=envelope.side,
                size_band=envelope.size_band,
                status="rejected",
                latency_ms=0,
                reason="Phase A clerk only fills the paper venue",
                created_at=datetime.now(UTC),
            )
        return ClerkFill(
            fill_id=str(uuid4()),
            envelope_id=envelope.envelope_id,
            venue="paper",
            side=envelope.side,
            size_band=envelope.size_band,
            status="paper_ack",
            latency_ms=1,
            reason=PAPER_ACK_REASON,
            created_at=datetime.now(UTC),
        )
