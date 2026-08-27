"""Live Rail venues cannot place orders in Phase A, even if armed."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.engines.paper_agent.types import PaperTrade
from app.engines.rail.clerk import RailClerk
from app.engines.rail.desk import RailDesk
from app.engines.rail.envelope import (
    assert_clerk_payload_is_blind,
    mint_from_paper_trade,
    mint_hl_envelope,
)
from app.engines.rail.venues.live import DriftVenue, HyperliquidVenue, PolymarketVenue
from app.engines.rail.venues.paper import PaperVenue
from app.engines.rail.venues.protocol import LiveVenueDisabled


def _trade() -> PaperTrade:
    now = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
    return PaperTrade(
        id=str(uuid4()),
        symbol="SOL",
        source="crypto_perp_v2",
        setup_type="perp_momentum",
        direction="long",
        fingerprint="fp",
        signal_at=now,
        confidence=70.0,
        opportunity_score=70.0,
        size_usd=2500.0,
        status="open",
        optimistic_entry=140.0,
        optimistic_entry_at=now,
        factors=["do not leak"],
        notes="thesis",
        stop_loss_pct=3.0,
    )


def test_paper_venue_acks_open_envelope() -> None:
    pair = mint_from_paper_trade(_trade())
    assert pair is not None
    envelope, sealed = pair
    fill = PaperVenue().submit(envelope, sealed)
    assert fill.status == "paper_ack"
    assert fill.venue == "paper"
    assert "BTC" not in fill.reason
    assert "SOL" not in fill.reason
    assert "thesis" not in fill.reason


@pytest.mark.parametrize("adapter_cls", [HyperliquidVenue, DriftVenue, PolymarketVenue])
def test_live_venues_refuse_even_when_armed(
    adapter_cls, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.config.settings.rail_armed", True)
    monkeypatch.setattr("app.config.settings.rail_live_enabled", True)
    pair = mint_from_paper_trade(_trade())
    assert pair is not None
    envelope, sealed = pair
    with pytest.raises(LiveVenueDisabled, match="Phase A/B is paper-only"):
        adapter_cls().submit(envelope, sealed)


def test_clerk_records_live_refuse_when_armed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.engines.rail.clerk.settings.rail_armed", True)
    pair = mint_from_paper_trade(_trade())
    assert pair is not None
    envelope, sealed = pair
    clerk = RailClerk()
    fill = clerk.submit(envelope, sealed, venue_id="hyperliquid")
    assert fill.status == "rejected"
    assert "Phase A/B is paper-only" in fill.reason
    assert fill.venue == "hyperliquid"


def test_desk_snapshot_is_blind_and_simulate_acks() -> None:
    class _One:
        def scan(self):
            return [
                mint_hl_envelope(
                    family="book",
                    instrument_key="SOL",
                    market_kind="perp",
                    side="buy",
                    edge_score=66.0,
                    invalidation="book_imbalance",
                )
            ]

    desk = RailDesk(scanner=_One())  # type: ignore[arg-type]
    snap = desk.snapshot()
    assert snap.phase == "B"
    assert snap.default_venue == "paper"
    assert snap.armed is False
    assert snap.live_enabled is False
    assert snap.sitting_out is False
    assert len(snap.envelopes) == 1
    payload = snap.envelopes[0].clerk_dict()
    assert_clerk_payload_is_blind(payload, banned_symbols=("SOL", "BTC", "HYPE"))
    envelope, fill = desk.simulate(snap.envelopes[0].envelope_id)
    assert envelope is not None
    assert fill is not None
    assert fill.status == "paper_ack"
