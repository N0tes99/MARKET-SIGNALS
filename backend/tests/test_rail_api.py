"""Rail desk API is clerk-blind and paper-only."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.service_dependencies import get_rail_desk
from app.engines.paper_agent.types import PaperAgentSummary, PaperLedgerSnapshot, PaperTrade
from app.engines.rail.desk import RailDesk
from app.main import app


def _trade(*, symbol: str = "BTC", source: str = "crypto_perp_v2") -> PaperTrade:
    now = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
    return PaperTrade(
        id=str(uuid4()),
        symbol=symbol,
        source=source,  # type: ignore[arg-type]
        setup_type="perp_momentum",
        direction="long",
        fingerprint="fp",
        signal_at=now,
        confidence=70.0,
        opportunity_score=70.0,
        size_usd=2500.0,
        status="open",
        optimistic_entry=64000.0,
        optimistic_entry_at=now,
        factors=["funding crowded"],
        notes="hidden thesis",
        stop_loss_pct=3.0,
    )


class _StubPaper:
    def __init__(self) -> None:
        self._open = [_trade(), _trade(symbol="SPY", source="equity_setup")]

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
            open_positions=1,
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
            open_trades=list(self._open),
            recent_closed=[],
        )


@pytest.fixture
async def rail_client():
    desk = RailDesk(paper_agent=_StubPaper())  # type: ignore[arg-type]
    app.dependency_overrides[get_rail_desk] = lambda: desk
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, desk
    app.dependency_overrides.pop(get_rail_desk, None)


@pytest.mark.asyncio
async def test_desk_omits_symbols_and_skips_equity(rail_client) -> None:
    client, _desk = rail_client
    res = await client.get("/api/v1/rail/desk")
    assert res.status_code == 200
    body = res.json()
    blob = str(body)
    assert "BTC" not in blob
    assert "SPY" not in blob
    assert "funding crowded" not in blob
    assert "hidden thesis" not in blob
    assert "64000" not in blob
    assert body["phase"] == "A"
    assert body["armed"] is False
    assert body["live_enabled"] is False
    assert body["default_venue"] == "paper"
    assert len(body["envelopes"]) == 1
    assert body["envelopes"][0]["target_venue"] == "hyperliquid"
    assert body["envelopes"][0]["venue"] == "paper"
    assert {row["id"] for row in body["venues"]} == {
        "paper",
        "hyperliquid",
        "drift",
        "polymarket",
    }


@pytest.mark.asyncio
async def test_simulate_paper_ack(rail_client) -> None:
    client, _desk = rail_client
    desk_res = await client.get("/api/v1/rail/desk")
    envelope_id = desk_res.json()["envelopes"][0]["envelope_id"]
    res = await client.post(
        "/api/v1/rail/clerk/simulate",
        json={"envelope_id": envelope_id},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["fill"]["status"] == "paper_ack"
    assert "BTC" not in str(body)


@pytest.mark.asyncio
async def test_simulate_unknown_envelope(rail_client) -> None:
    client, _desk = rail_client
    res = await client.post(
        "/api/v1/rail/clerk/simulate",
        json={"envelope_id": "paper:missing"},
    )
    assert res.status_code == 200
    assert res.json()["ok"] is False
