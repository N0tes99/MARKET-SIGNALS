"""Build the nested Rail desk snapshot from Hyperliquid-native scanners."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock

from app.config import settings
from app.engines.rail.clerk import RailClerk
from app.engines.rail.scanners import HyperliquidRailScanner
from app.engines.rail.types import (
    ClerkFill,
    OpportunityEnvelope,
    RailDeskSnapshot,
    SealedInstrument,
    VenueInfo,
)

VENUE_CATALOG: tuple[VenueInfo, ...] = (
    VenueInfo(
        id="paper",
        label="Paper",
        chain="off-chain",
        market_kind="perp",
        role="Phase A/B fill venue — dry-run only",
        status="ready",
        note="Acks clerk submits. No live order. No second paper ledger.",
    ),
    VenueInfo(
        id="hyperliquid",
        label="Hyperliquid",
        chain="hyperliquid-l1",
        market_kind="perp",
        role="Identify live (books, funding, HIP-4). Execute later via agent wallet.",
        status="ready",
        note="Phase B reads /info. Live /exchange stays refused.",
    ),
    VenueInfo(
        id="drift",
        label="Drift",
        chain="solana",
        market_kind="perp",
        role="Solana OSS perp option",
        status="planned",
        note="Not first — we only scan rails we can fill. Phase B is Hyperliquid.",
    ),
    VenueInfo(
        id="polymarket",
        label="Polymarket",
        chain="polygon",
        market_kind="prediction",
        role="Prediction CLOB — only if HL does not list the book",
        status="planned",
        note="HIP-4 already puts outcomes on the HL rail. No Polymarket scanner yet.",
    ),
)


class EnvelopeBook:
    """In-memory envelope registry keyed by envelope_id."""

    def __init__(self) -> None:
        self._envelopes: dict[str, OpportunityEnvelope] = {}
        self._sealed: dict[str, SealedInstrument] = {}
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self._envelopes.clear()
            self._sealed.clear()

    def upsert(self, envelope: OpportunityEnvelope, sealed: SealedInstrument) -> None:
        with self._lock:
            self._envelopes[envelope.envelope_id] = envelope
            self._sealed[envelope.envelope_id] = sealed

    def get(
        self, envelope_id: str
    ) -> tuple[OpportunityEnvelope, SealedInstrument] | None:
        with self._lock:
            envelope = self._envelopes.get(envelope_id)
            sealed = self._sealed.get(envelope_id)
            if envelope is None or sealed is None:
                return None
            return envelope, sealed

    def list_envelopes(self) -> list[OpportunityEnvelope]:
        with self._lock:
            rows = list(self._envelopes.values())
        rows.sort(key=lambda item: item.created_at, reverse=True)
        return rows


class RailDesk:
    """Mint blind envelopes from HL scanners and run the paper clerk."""

    def __init__(
        self,
        *,
        scanner: HyperliquidRailScanner | None = None,
        clerk: RailClerk | None = None,
        paper_agent: object | None = None,
    ) -> None:
        del paper_agent
        self._scanner = scanner or HyperliquidRailScanner()
        self.clerk = clerk or RailClerk()
        self.book = EnvelopeBook()

    def reset(self) -> None:
        self.book.reset()
        self.clerk.reset()

    def snapshot(self) -> RailDeskSnapshot:
        pairs = self._scanner.scan()
        self.book.reset()
        families: dict[str, int] = {"book": 0, "funding": 0, "outcome": 0}
        for envelope, sealed in pairs:
            self.book.upsert(envelope, sealed)
            if sealed.family in families:
                families[sealed.family] += 1
        envelopes = self.book.list_envelopes()
        open_n = sum(1 for item in envelopes if item.status == "open")
        notes = [
            "phase_b_hl_scanners",
            f"minted:{len(envelopes)}",
            f"book:{families['book']}",
            f"funding:{families['funding']}",
            f"outcome:{families['outcome']}",
            "live_venues_refuse",
        ]
        if open_n == 0:
            notes.append("sitting_out")
        return RailDeskSnapshot(
            as_of=datetime.now(UTC),
            armed=bool(settings.rail_armed),
            live_enabled=bool(settings.rail_live_enabled),
            phase="B",
            default_venue="paper",
            sitting_out=open_n == 0,
            venues=list(VENUE_CATALOG),
            envelopes=envelopes,
            fills=self.clerk.fills(),
            notes=notes,
        )

    def simulate(
        self, envelope_id: str
    ) -> tuple[OpportunityEnvelope | None, ClerkFill | None]:
        pair = self.book.get(envelope_id)
        if pair is None:
            self.snapshot()
            pair = self.book.get(envelope_id)
        if pair is None:
            return None, None
        envelope, sealed = pair
        fill = self.clerk.submit(envelope, sealed, venue_id="paper")
        return envelope, fill
