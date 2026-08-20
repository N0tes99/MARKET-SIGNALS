"""Scoped API key auth tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.api_keys import (
    API_KEY_PREFIX,
    generate_api_key,
    hash_api_key,
    normalize_scopes,
    required_scope_for_path,
    scope_allows,
)
from app.core.dependencies import get_db
from app.core.security import hash_password
from app.database.base import Base
from app.main import app
from app.models import AccessGrantModel, ApiKeyModel, User  # noqa: F401


def test_normalize_scopes_dedupes() -> None:
    assert normalize_scopes(["expansion:read", "cortex:read"]) == [
        "expansion:read",
        "cortex:read",
    ]


def test_normalize_scopes_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown scope"):
        normalize_scopes(["nope:read"])


def test_required_scope_for_path_expansion() -> None:
    assert required_scope_for_path("/api/v1/expansion", "GET") == "expansion:read"
    assert required_scope_for_path("/api/v1/expansion/BTC", "GET") == "expansion:read"
    assert required_scope_for_path("/api/v1/expansion", "POST") is None


def test_scope_allows_wildcard() -> None:
    assert scope_allows("cortex:read", ("*:read",))


def test_generate_api_key_format() -> None:
    full, prefix, digest = generate_api_key()
    assert full.startswith(API_KEY_PREFIX)
    assert prefix == full[:16]
    assert digest == hash_api_key(full)


async def _postgres_available() -> bool:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


@pytest.fixture
async def api_key_client(monkeypatch: pytest.MonkeyPatch):
    if not await _postgres_available():
        pytest.skip("Postgres not available")

    import pyotp

    secret = pyotp.random_base32()
    monkeypatch.setattr("app.core.site_gate.settings.site_totp_secret", secret)
    monkeypatch.setattr("app.config.settings.site_totp_secret", secret)
    monkeypatch.setattr("app.core.site_gate.settings.auth_password", "gate-pass")
    monkeypatch.setattr("app.config.settings.auth_password", "gate-pass")

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        builder = User(
            id=uuid.uuid4(),
            email="builder@test.local",
            username="builder",
            password_hash=hash_password("builderpass1"),
            email_verified_at=datetime.now(UTC),
        )
        session.add(builder)
        await session.commit()

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, factory, builder.id

    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


@pytest.mark.asyncio
async def test_api_key_requires_grant(api_key_client) -> None:
    client, factory, user_id = api_key_client
    full_key, prefix, digest = generate_api_key()

    async with factory() as session:
        session.add(
            ApiKeyModel(
                user_id=user_id,
                name="test",
                key_prefix=prefix,
                key_hash=digest,
                scopes=["expansion:read"],
            )
        )
        await session.commit()

    res = await client.get(
        "/api/v1/expansion",
        headers={"Authorization": f"Bearer {full_key}"},
    )
    assert res.status_code == 401
    assert res.json()["code"] == "ACCESS_NOT_GRANTED"


@pytest.mark.asyncio
async def test_api_key_bypasses_mfa_with_scope(api_key_client) -> None:
    client, factory, user_id = api_key_client
    full_key, prefix, digest = generate_api_key()

    async with factory() as session:
        session.add(
            AccessGrantModel(
                user_id=user_id,
                expires_at=datetime.now(UTC) + timedelta(days=30),
                notes="test",
            )
        )
        session.add(
            ApiKeyModel(
                user_id=user_id,
                name="builder",
                key_prefix=prefix,
                key_hash=digest,
                scopes=["expansion:read", "cortex:read"],
            )
        )
        await session.commit()

    res = await client.get(
        "/api/v1/expansion",
        headers={"X-API-Key": full_key},
    )
    assert res.status_code == 200
    body = res.json()
    assert "candidates" in body

    cortex = await client.get(
        "/api/v1/cortex",
        headers={"Authorization": f"Bearer {full_key}"},
    )
    assert cortex.status_code == 200
    assert "tick_id" in cortex.json()


@pytest.mark.asyncio
async def test_api_key_insufficient_scope(api_key_client) -> None:
    client, factory, user_id = api_key_client
    full_key, prefix, digest = generate_api_key()

    async with factory() as session:
        session.add(
            AccessGrantModel(
                user_id=user_id,
                expires_at=datetime.now(UTC) + timedelta(days=30),
                notes="test",
            )
        )
        session.add(
            ApiKeyModel(
                user_id=user_id,
                name="expansion-only",
                key_prefix=prefix,
                key_hash=digest,
                scopes=["expansion:read"],
            )
        )
        await session.commit()

    res = await client.get(
        "/api/v1/cortex",
        headers={"X-API-Key": full_key},
    )
    assert res.status_code == 403
    assert res.json()["code"] == "INSUFFICIENT_SCOPE"


@pytest.mark.asyncio
async def test_session_still_requires_mfa(api_key_client) -> None:
    client, factory, user_id = api_key_client
    from app.core.security import create_access_token

    async with factory() as session:
        session.add(
            AccessGrantModel(
                user_id=user_id,
                expires_at=datetime.now(UTC) + timedelta(days=30),
                notes="test",
            )
        )
        await session.commit()

    session_tok = create_access_token(user_id)
    res = await client.get(
        "/api/v1/expansion",
        cookies={"se_session": session_tok},
    )
    assert res.status_code == 401
    assert res.json()["code"] == "MFA_REQUIRED"


@pytest.mark.asyncio
async def test_api_key_bypasses_basic_auth(api_key_client) -> None:
    client, factory, user_id = api_key_client
    full_key, prefix, digest = generate_api_key()

    async with factory() as session:
        session.add(
            AccessGrantModel(
                user_id=user_id,
                expires_at=datetime.now(UTC) + timedelta(days=30),
                notes="test",
            )
        )
        session.add(
            ApiKeyModel(
                user_id=user_id,
                name="direct",
                key_prefix=prefix,
                key_hash=digest,
                scopes=["expansion:read"],
            )
        )
        await session.commit()

    res = await client.get(
        "/api/v1/expansion",
        headers={"X-API-Key": full_key},
    )
    assert res.status_code == 200
    assert res.json().get("code") != "Unauthorized"
