"""Social auth and discussion API tests (skipped when Postgres unavailable)."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.dependencies import get_db
from app.core.security import (
    SESSION_COOKIE_NAME,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.database.base import Base
from app.main import app
from app.models import Comment, Favorite, Follow, Post, PostLike, User  # noqa: F401


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("securepass1")
    assert verify_password("securepass1", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_roundtrip() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    assert decode_access_token(token) == user_id
    assert decode_access_token("not-a-token") is None


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
async def social_client():
    """Async client with tables ensured and isolated DB session override."""
    if not await _postgres_available():
        pytest.skip("Postgres not available")

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

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
        yield client, factory
    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


async def _register_verified(client: AsyncClient, factory, *, prefix: str = "user") -> dict:
    """Register and force-verify so write APIs work in tests without SMTP."""
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}_{suffix}@example.com"
    username = f"{prefix}_{suffix}"
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": "password123"},
    )
    assert register.status_code == 201

    async with factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        user.email_verified_at = datetime.now(UTC)
        user.email_verify_token_hash = None
        await session.commit()

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    assert login.status_code == 200
    assert login.json()["email_verified"] is True
    return login.json()


@pytest.mark.asyncio
async def test_register_login_me(social_client) -> None:
    client, factory = social_client
    suffix = uuid.uuid4().hex[:8]
    email = f"user_{suffix}@example.com"
    username = f"user_{suffix}"

    register = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": "password123"},
    )
    assert register.status_code == 201
    body = register.json()
    assert body["email"] == email
    assert body["username"] == username
    assert "email_verified" in body

    # Dev without SMTP auto-verifies + sets cookie; production path does not.
    # Either way login should work after we ensure verified.
    async with factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        user.email_verified_at = datetime.now(UTC)
        await session.commit()

    await client.post("/api/v1/auth/logout")
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    assert login.status_code == 200
    assert SESSION_COOKIE_NAME in login.cookies

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == username


@pytest.mark.asyncio
async def test_create_post_tracked_and_untracked(social_client) -> None:
    client, factory = social_client
    await _register_verified(client, factory, prefix="poster")

    untracked = await client.post(
        "/api/v1/assets/NOTREAL/posts",
        json={"body": "should fail"},
    )
    assert untracked.status_code == 400

    created = await client.post(
        "/api/v1/assets/BTC/posts",
        json={"body": "BTC looking constructive"},
    )
    assert created.status_code == 201
    post = created.json()
    assert post["symbol"] == "BTC"
    assert post["like_count"] == 0

    like = await client.post(f"/api/v1/posts/{post['id']}/like")
    assert like.status_code == 204

    feed = await client.get("/api/v1/social/feed")
    assert feed.status_code == 200
    match = next(p for p in feed.json() if p["id"] == post["id"])
    assert match["liked_by_me"] is True
    assert match["like_count"] >= 1

    comment = await client.post(
        f"/api/v1/posts/{post['id']}/comments",
        json={"body": "Agreed"},
    )
    assert comment.status_code == 201

    await client.post("/api/v1/auth/logout")
    denied = await client.post(
        "/api/v1/assets/BTC/posts",
        json={"body": "no auth"},
    )
    assert denied.status_code == 401


@pytest.mark.asyncio
async def test_follow_and_favorites(social_client) -> None:
    client, factory = social_client
    a = await _register_verified(client, factory, prefix="alice")
    await client.post("/api/v1/auth/logout")
    await _register_verified(client, factory, prefix="bob")

    follow = await client.post(f"/api/v1/users/{a['id']}/follow")
    assert follow.status_code == 204

    profile = await client.get(f"/api/v1/users/{a['username']}")
    assert profile.status_code == 200
    assert profile.json()["followed_by_me"] is True
    assert profile.json()["follower_count"] >= 1

    fav = await client.put("/api/v1/me/favorites", json={"symbol": "ETH"})
    assert fav.status_code == 201
    assert fav.json()["symbol"] == "ETH"

    listed = await client.get("/api/v1/me/favorites")
    assert listed.status_code == 200
    assert any(f["symbol"] == "ETH" for f in listed.json())

    bad = await client.put("/api/v1/me/favorites", json={"symbol": "NOPE"})
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_forgot_and_reset_password(social_client) -> None:
    client, factory = social_client
    suffix = uuid.uuid4().hex[:8]
    email = f"reset_{suffix}@example.com"
    username = f"reset_{suffix}"

    register = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": "oldpass123"},
    )
    assert register.status_code == 201

    unknown = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": f"missing_{suffix}@example.com"},
    )
    assert unknown.status_code == 204

    forgot = await client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert forgot.status_code == 204

    async with factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        assert user.password_reset_token_hash is not None

    # Replace with a known raw token so we can exercise reset-password
    raw = secrets.token_urlsafe(32)
    async with factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        user.password_reset_token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        user.password_reset_sent_at = datetime.now(UTC)
        await session.commit()

    bad_token = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "not-a-real-token-value", "password": "newpass123"},
    )
    assert bad_token.status_code == 400

    reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "password": "newpass123"},
    )
    assert reset.status_code == 200
    assert SESSION_COOKIE_NAME in reset.cookies

    await client.post("/api/v1/auth/logout")
    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "oldpass123"},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "newpass123"},
    )
    assert new_login.status_code == 200

    async with factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        assert user.password_reset_token_hash is None
