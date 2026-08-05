"""Social auth and discussion API tests (skipped when Postgres unavailable)."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
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
from app.models import Comment, Post, User  # noqa: F401 — register metadata


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
        yield client
    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


@pytest.mark.asyncio
async def test_register_login_me(social_client: AsyncClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    email = f"user_{suffix}@example.com"
    username = f"user_{suffix}"

    register = await social_client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": "password123"},
    )
    assert register.status_code == 201
    body = register.json()
    assert body["email"] == email
    assert body["username"] == username
    assert SESSION_COOKIE_NAME in register.cookies

    me = await social_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == username

    await social_client.post("/api/v1/auth/logout")
    logged_out = await social_client.get("/api/v1/auth/me")
    assert logged_out.status_code == 401

    login = await social_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    assert login.status_code == 200
    assert login.json()["username"] == username
    me_again = await social_client.get("/api/v1/auth/me")
    assert me_again.status_code == 200


@pytest.mark.asyncio
async def test_create_post_tracked_and_untracked(social_client: AsyncClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    await social_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"poster_{suffix}@example.com",
            "username": f"poster_{suffix}",
            "password": "password123",
        },
    )

    untracked = await social_client.post(
        "/api/v1/assets/NOTREAL/posts",
        json={"body": "should fail"},
    )
    assert untracked.status_code == 400

    created = await social_client.post(
        "/api/v1/assets/BTC/posts",
        json={"body": "BTC looking constructive"},
    )
    assert created.status_code == 201
    post = created.json()
    assert post["symbol"] == "BTC"
    assert post["body"] == "BTC looking constructive"
    assert post["username"].startswith("poster_")
    assert post["comment_count"] == 0

    listed = await social_client.get("/api/v1/assets/BTC/posts")
    assert listed.status_code == 200
    assert any(p["id"] == post["id"] for p in listed.json())

    comment = await social_client.post(
        f"/api/v1/posts/{post['id']}/comments",
        json={"body": "Agreed"},
    )
    assert comment.status_code == 201
    assert comment.json()["body"] == "Agreed"

    # Anonymous write should fail
    await social_client.post("/api/v1/auth/logout")
    denied = await social_client.post(
        "/api/v1/assets/BTC/posts",
        json={"body": "no auth"},
    )
    assert denied.status_code == 401
