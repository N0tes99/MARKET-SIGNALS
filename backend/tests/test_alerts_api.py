"""Alert API tests."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.auth_deps import get_current_user, require_admin_user
from app.main import app
from app.models.user import User


def _admin_user() -> User:
    return User(
        id=uuid4(),
        email="admin@test.local",
        username="Admin",
        password_hash="test",
        email_verified_at=datetime.now(UTC),
    )


def _non_admin_user() -> User:
    return User(
        id=uuid4(),
        email="user@test.local",
        username="notadmin",
        password_hash="test",
        email_verified_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_alert_status(client: AsyncClient) -> None:
    response = await client.get("/api/v1/alerts/status")
    assert response.status_code == 200
    data = response.json()
    assert "enabled" in data
    assert data["min_grade"] == "B"
    assert data["min_confidence"] == 65.0
    assert "discord_configured" in data
    assert "email_configured" in data


@pytest.mark.asyncio
async def test_alert_test_allowed_for_admin(client: AsyncClient) -> None:
    response = await client.post("/api/v1/alerts/test", json={"channel": "discord"})
    assert response.status_code == 200
    assert response.json()["symbol"] == "TEST"


@pytest.mark.asyncio
async def test_alert_test_requires_admin(client: AsyncClient) -> None:
    app.dependency_overrides.pop(require_admin_user, None)
    try:
        response = await client.post("/api/v1/alerts/test", json={"channel": "discord"})
        assert response.status_code in {401, 403}
    finally:
        app.dependency_overrides[require_admin_user] = _admin_user


@pytest.mark.asyncio
async def test_alert_check_requires_admin(client: AsyncClient) -> None:
    app.dependency_overrides.pop(require_admin_user, None)
    app.dependency_overrides[get_current_user] = _non_admin_user
    try:
        response = await client.post("/api/v1/alerts/check")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[require_admin_user] = _admin_user
