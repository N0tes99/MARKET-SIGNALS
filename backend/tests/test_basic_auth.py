"""Basic Auth and CORS settings tests."""

import base64

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.basic_auth import credentials_valid, is_public_path, parse_basic_auth
from app.main import app


def test_health_is_public_path() -> None:
    assert is_public_path("/api/v1/health")
    assert is_public_path("/api/v1/auth/gate/verify") is False


def test_parse_basic_auth() -> None:
    token = base64.b64encode(b"signal:secret").decode()
    assert parse_basic_auth(f"Basic {token}") == ("signal", "secret")
    assert parse_basic_auth(None) is None
    assert parse_basic_auth("Bearer x") is None


def test_credentials_valid(monkeypatch) -> None:
    monkeypatch.setattr("app.core.basic_auth.settings.auth_username", "signal")
    monkeypatch.setattr("app.core.basic_auth.settings.auth_password", "secret")
    assert credentials_valid("signal", "secret")
    assert not credentials_valid("signal", "wrong")


@pytest.mark.asyncio
async def test_auth_disabled_allows_requests(monkeypatch) -> None:
    monkeypatch.setattr("app.core.basic_auth.settings.auth_password", "")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_auth_enabled_requires_credentials(monkeypatch) -> None:
    monkeypatch.setattr("app.core.basic_auth.settings.auth_username", "signal")
    monkeypatch.setattr("app.core.basic_auth.settings.auth_password", "secret")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        unauthorized = await client.get("/api/v1/alerts/status")
        assert unauthorized.status_code == 401
        assert unauthorized.headers.get("www-authenticate", "").lower().startswith("basic")

        health = await client.get("/api/v1/health")
        assert health.status_code == 200

        token = base64.b64encode(b"signal:secret").decode()
        ok = await client.get(
            "/api/v1/alerts/status",
            headers={"Authorization": f"Basic {token}"},
        )
        assert ok.status_code == 200


def test_normalize_database_url() -> None:
    from app.config.settings import Settings

    normalized = Settings.normalize_database_url("postgres://user:pass@host:5432/db")
    assert isinstance(normalized, str)
    assert normalized.startswith("postgresql+asyncpg://")
