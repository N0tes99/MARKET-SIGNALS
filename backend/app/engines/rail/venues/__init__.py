"""Venue registry. Live adapters are refuse-only in Phase A."""

from app.engines.rail.venues.live import DriftVenue, HyperliquidVenue, PolymarketVenue
from app.engines.rail.venues.paper import PaperVenue
from app.engines.rail.venues.protocol import LiveVenueDisabled, VenueAdapter

__all__ = [
    "DriftVenue",
    "HyperliquidVenue",
    "LiveVenueDisabled",
    "PaperVenue",
    "PolymarketVenue",
    "VenueAdapter",
    "VENUES",
]

VENUES: dict[str, VenueAdapter] = {
    "paper": PaperVenue(),
    "hyperliquid": HyperliquidVenue(),
    "drift": DriftVenue(),
    "polymarket": PolymarketVenue(),
}
