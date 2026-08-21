"""Live Rail venues cannot place orders in Phase A, even if armed."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.engines.paper_agent.types import PaperAgentSummary, PaperLedgerSnapshot, PaperTrade
from app.engines.rail.clerk import RailClerk
from app.engines.rail.desk import RailDesk
from app.engines.rail.envelope import mint_from_paper_trade
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
    with pytest.raises(LiveVenueDisabled, match="Phase A is paper-only"):
        adapter_cls().submit(envelope, sealed)


def test_clerk_records_live_refuse_when_armed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.engines.rail.clerk.settings.rail_armed", True)
    pair = mint_from_paper_trade(_trade())
    assert pair is not None
    envelope, sealed = pair
    clerk = RailClerk()
    fill = clerk.submit(envelope, sealed, venue_id="hyperliquid")
    assert fill.status == "rejected"
    assert "Phase A is paper-only" in fill.reason
    assert fill.venue == "hyperliquid"


class _StubPaper:
    def __init__(self, trades: list[PaperTrade]) -> None:
        self._trades = trades

    def summary(self, *, tick_notes=None):
        now = datetime.now(UTC)
        empty = PaperLedgerSnapshot(
            label="x",
            starting_cash=0,
            equity=0,
            realized_pnl=0,
            unrealized_pnl=0,
            total_pnl=0,
            return_pct=0,
            open_positions=0,
            closed_trades=0,
            wins=0,
            losses=0,
        )
        return PaperAgentSummary(
            agent_name="stub",
            starting_cash=0,
            as_of=now,
            last_tick_at=None,
            optimistic=empty,
            honest=empty,
            open_trades=[t for t in self._trades if t.status == "open"],
            recent_closed=[t for t in self._trades if t.status == "closed"],
        )


def test_desk_snapshot_is_blind_and_simulate_acks() -> None:
    desk = RailDesk(paper_agent=_StubPaper([_trade()]))  # type: ignore[arg-type]
    snap = desk.snapshot()
    assert snap.phase == "A"
    assert snap.default_venue == "paper"
    assert snap.armed is False
    assert snap.live_enabled is False
    assert snap.sitting_out is False
    assert len(snap.envelopes) == 1
    payload = snap.envelopes[0].clerk_dict()
    blob = str(payload)
    assert "SOL" not in blob
    assert "do not leak" not in blob
    envelope, fill = desk.simulate(snap.envelopes[0].envelope_id)
    assert envelope is not None
    assert fill is not None
    assert fill.status == "paper_ack"
