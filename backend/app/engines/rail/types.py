"""Surface 6 Rail — clerk-visible types. No symbol, thesis, or prices."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

VenueId = Literal["paper", "hyperliquid", "drift", "polymarket"]
MarketKind = Literal["perp", "prediction"]
Side = Literal["buy", "sell"]
SizeBand = Literal["xs", "s", "m", "l"]
Urgency = Literal["passive", "normal", "aggressive"]
EnvelopeStatus = Literal["open", "closed"]
FillStatus = Literal["paper_ack", "rejected"]

CLERK_FORBIDDEN_FIELDS = frozenset(
    {
        "symbol",
        "factors",
        "notes",
        "thesis",
        "price",
        "entry",
        "mark",
        "setup_type",
        "fingerprint",
    }
)

CRYPTO_PAPER_SOURCES = frozenset(
    {
        "crypto_setup",
        "crypto_perp_v2",
        "squeeze_expansion",
    }
)


@dataclass(frozen=True)
class OpportunityEnvelope:
    """What the clerk is allowed to see."""

    envelope_id: str
    venue: VenueId
    target_venue: VenueId
    market_kind: MarketKind
    side: Side
    size_band: SizeBand
    urgency: Urgency
    edge_score: float
    ttl_seconds: int
    invalidation: str
    instrument_handle: str
    status: EnvelopeStatus
    created_at: datetime

    def clerk_dict(self) -> dict[str, object]:
        """JSON-safe clerk payload. Must never include thesis fields."""
        return {
            "envelope_id": self.envelope_id,
            "venue": self.venue,
            "target_venue": self.target_venue,
            "market_kind": self.market_kind,
            "side": self.side,
            "size_band": self.size_band,
            "urgency": self.urgency,
            "edge_score": round(float(self.edge_score), 2),
            "ttl_seconds": int(self.ttl_seconds),
            "invalidation": self.invalidation,
            "instrument_handle": self.instrument_handle,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class SealedInstrument:
    """Adapter-only resolution. Never serialized on /rail."""

    handle: str
    venue: VenueId
    symbol: str
    market_kind: MarketKind
    paper_trade_id: str | None = None


@dataclass
class ClerkFill:
    """Dry-run or rejected submit. Blind like the envelope."""

    fill_id: str
    envelope_id: str
    venue: VenueId
    side: Side
    size_band: SizeBand
    status: FillStatus
    latency_ms: int
    reason: str
    created_at: datetime

    def clerk_dict(self) -> dict[str, object]:
        return {
            "fill_id": self.fill_id,
            "envelope_id": self.envelope_id,
            "venue": self.venue,
            "side": self.side,
            "size_band": self.size_band,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "reason": self.reason,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class VenueInfo:
    """Catalog row for the nested Rail site."""

    id: VenueId
    label: str
    chain: str
    market_kind: MarketKind
    role: str
    status: Literal["ready", "planned", "refused"]
    note: str


@dataclass
class RailDeskSnapshot:
    """Nested-site payload."""

    as_of: datetime
    armed: bool
    live_enabled: bool
    phase: str
    default_venue: VenueId
    sitting_out: bool
    venues: list[VenueInfo]
    envelopes: list[OpportunityEnvelope]
    fills: list[ClerkFill]
    notes: list[str] = field(default_factory=list)
