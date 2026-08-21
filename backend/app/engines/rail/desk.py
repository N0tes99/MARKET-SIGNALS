"""Build the nested Rail desk snapshot from the public paper agent book."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from typing import TYPE_CHECKING

from app.config import settings
from app.engines.rail.clerk import RailClerk
from app.engines.rail.envelope import mint_from_paper_trade
from app.engines.rail.types import (
    ClerkFill,
    OpportunityEnvelope,
    RailDeskSnapshot,
    SealedInstrument,
    VenueInfo,
)

if TYPE_CHECKING:
    from app.engines.paper_agent.agent import PaperAgent

VENUE_CATALOG: tuple[VenueInfo, ...] = (
    VenueInfo(
        id="paper",
        label="Paper",
        chain="off-chain",
        market_kind="perp",
        role="Phase A fill venue — dry-run only",
        status="ready",
        note="Reuses the public paper agent book. No second ledger. No live order.",
    ),
    VenueInfo(
        id="hyperliquid",
        label="Hyperliquid",
        chain="hyperliquid-l1",
        market_kind="perp",
        role="Primary live perp target (agent wallets)",
        status="planned",
        note="Best clerk venue for perps. Phase A adapter refuses all orders.",
    ),
    VenueInfo(
        id="drift",
        label="Drift",
        chain="solana",
        market_kind="perp",
        role="Solana OSS perp option",
        status="planned",
        note="Use if settlement must be Solana. Phase A adapter refuses all orders.",
    ),
    VenueInfo(
        id="polymarket",
        label="Polymarket",
        chain="polygon",
        market_kind="prediction",
        role="Prediction CLOB — separate market_kind",
        status="planned",
        note="Same clerk, different edge. No prediction envelopes in Phase A.",
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
    """Mint blind envelopes from paper crypto trades and run the clerk."""

    def __init__(self, *, paper_agent: PaperAgent, clerk: RailClerk | None = None) -> None:
        self._paper = paper_agent
        self.clerk = clerk or RailClerk()
        self.book = EnvelopeBook()

    def reset(self) -> None:
        self.book.reset()
        self.clerk.reset()

    def snapshot(self) -> RailDeskSnapshot:
        summary = self._paper.summary(tick_notes=[])
        trades = list(summary.open_trades) + list(summary.recent_closed)
        minted = 0
        skipped = 0
        self.book.reset()
        for trade in trades:
            pair = mint_from_paper_trade(trade)
            if pair is None:
                skipped += 1
                continue
            envelope, sealed = pair
            self.book.upsert(envelope, sealed)
            minted += 1
        envelopes = self.book.list_envelopes()
        open_n = sum(1 for item in envelopes if item.status == "open")
        notes = [
            "phase_a_paper_only",
            f"minted:{minted}",
            f"skipped_non_crypto:{skipped}",
            "live_venues_refuse",
        ]
        if open_n == 0:
            notes.append("sitting_out")
        return RailDeskSnapshot(
            as_of=datetime.now(UTC),
            armed=bool(settings.rail_armed),
            live_enabled=bool(settings.rail_live_enabled),
            phase="A",
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
            # Rebuild from current paper book, then retry once.
            self.snapshot()
            pair = self.book.get(envelope_id)
        if pair is None:
            return None, None
        envelope, sealed = pair
        fill = self.clerk.submit(envelope, sealed, venue_id="paper")
        return envelope, fill
