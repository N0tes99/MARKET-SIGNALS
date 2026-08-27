"""Live venue stubs — Phase A/B hard refuse. No HTTP, no keys, no orders."""

from __future__ import annotations

from app.config import settings
from app.engines.rail.types import ClerkFill, OpportunityEnvelope, SealedInstrument, VenueId
from app.engines.rail.venues.protocol import LiveVenueDisabled, VenueAdapter

_REFUSE = (
    "Phase A/B is paper-only. This adapter cannot place orders even if RAIL_ARMED "
    "or RAIL_LIVE_ENABLED is set, and even if venue keys were present."
)


class _RefusingLiveVenue:
    """Shared refuse path so Hyperliquid / Drift / Polymarket cannot diverge."""

    venue_id: VenueId

    def submit(
        self,
        envelope: OpportunityEnvelope,
        sealed: SealedInstrument,
    ) -> ClerkFill:
        del envelope, sealed
        # Settings are read so misconfig is visible in tests; they cannot enable live.
        _ = (settings.rail_armed, settings.rail_live_enabled)
        raise LiveVenueDisabled(self.venue_id, _REFUSE)


class HyperliquidVenue(_RefusingLiveVenue, VenueAdapter):
    """Primary live perp target (agent wallets). Not implemented."""

    venue_id = "hyperliquid"


class DriftVenue(_RefusingLiveVenue, VenueAdapter):
    """Solana OSS perp option. Not implemented."""

    venue_id = "drift"


class PolymarketVenue(_RefusingLiveVenue, VenueAdapter):
    """Polygon prediction CLOB. Not implemented."""

    venue_id = "polymarket"
