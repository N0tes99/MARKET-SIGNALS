"""Dashboard WebSocket + SSE live feed."""

import json

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.schemas.assets import AssetsDashboard


def _empty_dashboard(*_args, **_kwargs) -> AssetsDashboard:
    return AssetsDashboard(assets=[], ranking_status="warming")


def test_dashboard_websocket_open_when_auth_off(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.websocket._get_dashboard", _empty_dashboard)
    client = TestClient(app)
    with client.websocket_connect("/api/v1/ws/dashboard") as ws:
        data = json.loads(ws.receive_text())
    assert data["ranking_status"] == "warming"
    assert data["assets"] == []


def test_dashboard_websocket_rejects_when_auth_on(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.websocket.auth_enabled", lambda: True)
    client = TestClient(app)
    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/api/v1/ws/dashboard"),
    ):
        pytest.fail("authenticated-required websocket should not be accepted")
    assert exc_info.value.code == 4401


@pytest.mark.asyncio
async def test_dashboard_sse_streams_cached_payload(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.sse._get_dashboard", _empty_dashboard)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/sse/dashboard?once=true")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "data:" in response.text
    data_line = next(line for line in response.text.splitlines() if line.startswith("data:"))
    payload = json.loads(data_line.split(":", 1)[1])
    assert payload["ranking_status"] == "warming"
