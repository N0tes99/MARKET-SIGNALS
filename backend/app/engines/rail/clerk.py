"""Rail clerk — submits sealed envelopes to a venue. Never imports engines."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

from app.config import settings
from app.engines.rail.types import ClerkFill, OpportunityEnvelope, SealedInstrument, VenueId
from app.engines.rail.venues import VENUES
from app.engines.rail.venues.protocol import LiveVenueDisabled

MAX_FILLS = 200
SITTING_OUT_REASON = "kill switch off or live venue; clerk sits out"


def _as_venue(venue: str) -> VenueId:
    if venue == "hyperliquid":
        return "hyperliquid"
    if venue == "drift":
        return "drift"
    if venue == "polymarket":
        return "polymarket"
    return "paper"


class RailClerk:
    """Single writer for dry-run fills."""

    def __init__(self) -> None:
        self._fills: list[ClerkFill] = []
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self._fills.clear()

    def fills(self) -> list[ClerkFill]:
        with self._lock:
            return list(self._fills)

    def submit(
        self,
        envelope: OpportunityEnvelope,
        sealed: SealedInstrument,
        *,
        venue_id: str | None = None,
    ) -> ClerkFill:
        target = venue_id or envelope.venue
        adapter = VENUES.get(target)
        if adapter is None:
            fill = _reject(envelope, target, f"unknown venue {target}")
            return self._record(fill)

        if target != "paper" and not settings.rail_armed:
            fill = _reject(envelope, target, SITTING_OUT_REASON)
            return self._record(fill)

        try:
            fill = adapter.submit(envelope, sealed)
        except LiveVenueDisabled as exc:
            fill = _reject(envelope, exc.venue, exc.detail)
        return self._record(fill)

    def _record(self, fill: ClerkFill) -> ClerkFill:
        with self._lock:
            self._fills.append(fill)
            if len(self._fills) > MAX_FILLS:
                self._fills = self._fills[-MAX_FILLS:]
        return fill


def _reject(envelope: OpportunityEnvelope, venue: str, reason: str) -> ClerkFill:
    return ClerkFill(
        fill_id=str(uuid4()),
        envelope_id=envelope.envelope_id,
        venue=_as_venue(venue),
        side=envelope.side,
        size_band=envelope.size_band,
        status="rejected",
        latency_ms=0,
        reason=reason,
        created_at=datetime.now(UTC),
    )
