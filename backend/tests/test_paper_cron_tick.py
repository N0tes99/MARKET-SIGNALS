"""Paper cron-tick keep-warm endpoint."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_cron_tick_requires_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes.paper.settings.cron_secret", "test-cron-secret")
    monkeypatch.setattr("app.config.settings.cron_secret", "test-cron-secret")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        missing = await client.post("/api/v1/paper/cron-tick")
        assert missing.status_code == 401
        bad = await client.post(
            "/api/v1/paper/cron-tick",
            headers={"X-Cron-Secret": "wrong"},
        )
        assert bad.status_code == 401


@pytest.mark.asyncio
async def test_cron_tick_runs_with_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes.paper.settings.cron_secret", "test-cron-secret")
    monkeypatch.setattr("app.config.settings.cron_secret", "test-cron-secret")
    # Gate on would still allow this path; leave off for simpler deps
    monkeypatch.setattr("app.core.site_gate.settings.site_totp_secret", "")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/paper/cron-tick",
            headers={"X-Cron-Secret": "test-cron-secret"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "tick_notes" in body
