"""Weight tuning API tests."""

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
async def test_optimize_weights_endpoint(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tuning/optimize/BTC")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "BTC"
    assert data["recommended_preset"]
    assert len(data["results"]) >= 5


@pytest.mark.asyncio
async def test_apply_and_reset_weights(client: AsyncClient) -> None:
    optimize = await client.get("/api/v1/tuning/optimize/BTC")
    preset = optimize.json()["recommended_preset"]

    applied = await client.post("/api/v1/tuning/weights/apply", json={"preset": preset})
    assert applied.status_code == 200
    body = applied.json()
    assert body["preset"] == preset
    if preset != "default":
        assert body["regime_auto"] is False

    reset = await client.post("/api/v1/tuning/weights/reset")
    assert reset.status_code == 200
    assert reset.json()["preset"] == "default"
    assert reset.json()["regime_auto"] is True


@pytest.mark.asyncio
async def test_apply_and_reset_weights_require_admin(client: AsyncClient) -> None:
    app.dependency_overrides.pop(require_admin_user, None)
    app.dependency_overrides[get_current_user] = _non_admin_user
    try:
        applied = await client.post("/api/v1/tuning/weights/apply", json={"preset": "default"})
        assert applied.status_code == 403
        reset = await client.post("/api/v1/tuning/weights/reset")
        assert reset.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[require_admin_user] = _admin_user
