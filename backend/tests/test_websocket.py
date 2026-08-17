"""Dashboard WebSocket auth."""

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app


def test_dashboard_websocket_rejects_unauthenticated() -> None:
    client = TestClient(app)
    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/api/v1/ws/dashboard"),
    ):
        pytest.fail("unauthenticated websocket should not be accepted")
    assert exc_info.value.code == 4401
