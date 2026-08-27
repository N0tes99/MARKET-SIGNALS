"""Rail desk API is clerk-blind and paper-only."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.service_dependencies import get_rail_desk
from app.engines.rail.desk import RailDesk
from app.engines.rail.envelope import assert_clerk_payload_is_blind, mint_hl_envelope
from app.main import app


class _StubScanner:
    def scan(self):
        return [
            mint_hl_envelope(
                family="funding",
                instrument_key="HYPE",
                market_kind="perp",
                side="sell",
                edge_score=70.0,
                invalidation="hl_funding",
            )
        ]


@pytest.fixture
async def rail_client():
    desk = RailDesk(scanner=_StubScanner())  # type: ignore[arg-type]
    app.dependency_overrides[get_rail_desk] = lambda: desk
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, desk
    app.dependency_overrides.pop(get_rail_desk, None)


@pytest.mark.asyncio
async def test_desk_omits_symbols_and_uses_phase_b(rail_client) -> None:
    client, _desk = rail_client
    res = await client.get("/api/v1/rail/desk")
    assert res.status_code == 200
    body = res.json()
    assert_clerk_payload_is_blind(body["envelopes"][0], banned_symbols=("HYPE", "BTC", "SOL"))
    assert body["phase"] == "B"
    assert body["armed"] is False
    assert body["live_enabled"] is False
    assert body["default_venue"] == "paper"
    assert len(body["envelopes"]) == 1
    assert body["envelopes"][0]["target_venue"] == "hyperliquid"
    assert body["envelopes"][0]["venue"] == "paper"
    assert body["envelopes"][0]["invalidation"] == "hl_funding"
    assert "phase_b_hl_scanners" in body["notes"]
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
    assert_clerk_payload_is_blind(body["fill"], banned_symbols=("HYPE", "BTC", "SOL"))


@pytest.mark.asyncio
async def test_simulate_unknown_envelope(rail_client) -> None:
    client, _desk = rail_client
    res = await client.post(
        "/api/v1/rail/clerk/simulate",
        json={"envelope_id": "hl:missing"},
    )
    assert res.status_code == 200
    assert res.json()["ok"] is False
