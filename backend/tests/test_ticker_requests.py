"""Ticker request API smoke tests (auth boundaries)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_create_ticker_request_requires_login() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/ticker-requests",
            json={"symbol": "NVDA", "message": "please add"},
        )
    assert res.status_code in {401, 403}


@pytest.mark.asyncio
async def test_admin_list_requires_admin() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/ticker-requests/admin")
    assert res.status_code in {401, 403}
