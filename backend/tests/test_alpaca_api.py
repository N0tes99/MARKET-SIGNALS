"""API tests for Alpaca read-only mirror route."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.adapters.brokers import alpaca as alpaca_mod
from app.adapters.brokers.alpaca import (
    AlpacaAccountSnapshot,
    AlpacaMirrorSnapshot,
    AlpacaPosition,
    clear_alpaca_mirror_cache,
)


@pytest.fixture(autouse=True)
def _clear_mirror_cache():
    clear_alpaca_mirror_cache()
    yield
    clear_alpaca_mirror_cache()


@pytest.mark.asyncio
async def test_alpaca_mirror_unconfigured(client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_key", "")
    monkeypatch.setattr(alpaca_mod.settings, "alpaca_api_secret", "")
    resp = await client.get("/api/v1/brokers/alpaca/mirror")
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is False
    assert body["mode"] == "unconfigured"
    assert body["positions"] == []
    assert body["recent_fills"] == []


@pytest.mark.asyncio
async def test_alpaca_mirror_configured_payload(client: AsyncClient, monkeypatch) -> None:
    snap = AlpacaMirrorSnapshot(
        configured=True,
        mode="paper",
        base_url="https://paper-api.alpaca.markets",
        as_of=datetime(2026, 8, 11, 12, 0, tzinfo=UTC),
        cached=False,
        error=None,
        account=AlpacaAccountSnapshot(
            equity=100_000.0,
            cash=40_000.0,
            buying_power=80_000.0,
            portfolio_value=100_000.0,
            status="ACTIVE",
        ),
        positions=[
            AlpacaPosition(
                symbol="AAPL",
                qty=10.0,
                side="long",
                market_value=1900.0,
                cost_basis=1800.0,
                unrealized_pl=100.0,
                unrealized_plpc=0.055,
                current_price=190.0,
                avg_entry_price=180.0,
                change_today=0.01,
            )
        ],
        recent_fills=[],
    )
    monkeypatch.setattr(
        "app.api.routes.alpaca.fetch_alpaca_mirror",
        lambda **kwargs: snap,
    )
    resp = await client.get("/api/v1/brokers/alpaca/mirror")
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is True
    assert body["mode"] == "paper"
    assert body["account"]["equity"] == 100000.0
    assert body["positions"][0]["symbol"] == "AAPL"
