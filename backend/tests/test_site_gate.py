"""Access gate: login → grant → per-user TOTP."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pyotp
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.core.security import JWT_ALGORITHM, create_access_token, hash_password
from app.core.site_gate import MFA_COOKIE_NAME, create_mfa_token, decode_mfa_token, verify_totp_code
from app.database import session as db_session
from app.database.base import Base
from app.main import app
from app.models import AccessGrantModel, User  # noqa: F401
from app.schemas.cme_futures import CmeFuturesBoardSchema


@pytest.fixture
def totp_secret(monkeypatch: pytest.MonkeyPatch) -> str:
    secret = pyotp.random_base32()
    monkeypatch.setattr("app.core.site_gate.settings.site_totp_secret", secret)
    monkeypatch.setattr("app.config.settings.site_totp_secret", secret)
    return secret


@pytest.mark.asyncio
async def test_gate_status_open_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.site_gate.settings.site_totp_secret", "")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/auth/gate/status")
    assert res.status_code == 200
    body = res.json()
    assert body["enabled"] is False
    assert body["next_step"] == "open"


@pytest.mark.asyncio
async def test_data_requires_login_when_gate_on(totp_secret: str) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/paper/summary?tick=false")
    assert res.status_code == 401
    assert res.json()["code"] == "LOGIN_REQUIRED"


@pytest.mark.asyncio
async def test_public_preview_allowed_when_gate_on(totp_secret: str) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/public/preview")
    assert res.status_code == 200
    body = res.json()
    assert "hot_picks" in body
    assert "optimistic" in body
    assert "honest" in body
    assert "total_pnl" in body["optimistic"]


@pytest.mark.asyncio
async def test_assets_list_requires_login_when_gate_on(totp_secret: str) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/assets")
    assert res.status_code == 401
    assert res.json()["code"] == "LOGIN_REQUIRED"


@pytest.mark.asyncio
async def test_assets_list_allowed_with_cron_secret_when_gate_on(
    totp_secret: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.site_gate.settings.cron_secret", "test-cron-secret")
    monkeypatch.setattr("app.config.settings.cron_secret", "test-cron-secret")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/v1/assets",
            headers={"X-Cron-Secret": "test-cron-secret"},
        )
    assert res.status_code != 401
    assert res.json().get("code") != "LOGIN_REQUIRED"


@pytest.mark.asyncio
async def test_forged_mfa_session_is_rejected_when_gate_on(totp_secret: str) -> None:
    """MFA cookies for a user id that does not exist (or has no grant) are not enough."""
    uid = uuid4()
    session = create_access_token(uid)
    mfa = create_mfa_token(
        user_id=uid,
        grant_expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/v1/assets",
            cookies={"se_session": session, MFA_COOKIE_NAME: mfa},
        )
    assert res.status_code in {401, 403}
    assert res.json().get("code") in {"LOGIN_REQUIRED", "ACCESS_NOT_GRANTED"}


@pytest.mark.asyncio
async def test_futures_board_requires_login_when_gate_on(totp_secret: str) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/futures/board")
    assert res.status_code == 401
    assert res.json()["code"] == "LOGIN_REQUIRED"


@pytest.mark.asyncio
async def test_futures_board_allowed_with_cron_secret_when_gate_on(
    totp_secret: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.site_gate.settings.cron_secret", "test-cron-secret")
    monkeypatch.setattr("app.config.settings.cron_secret", "test-cron-secret")
    monkeypatch.setattr(
        "app.api.routes.futures.build_cme_futures_board",
        lambda **kwargs: CmeFuturesBoardSchema(
            rows=[],
            scanned_at=datetime.now(UTC),
            symbols_scanned=0,
            universe=[],
            source="yahoo",
        ),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/v1/futures/board",
            headers={"X-Cron-Secret": "test-cron-secret"},
        )
    assert res.status_code != 401
    assert res.json().get("code") != "LOGIN_REQUIRED"


@pytest.mark.asyncio
async def test_runners_and_perps_still_require_login_with_cron_when_gate_on(
    totp_secret: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.site_gate.settings.cron_secret", "test-cron-secret")
    monkeypatch.setattr("app.config.settings.cron_secret", "test-cron-secret")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"X-Cron-Secret": "test-cron-secret"}
        runners = await client.get("/api/v1/runners", headers=headers)
        perps = await client.get("/api/v1/perps/board", headers=headers)
        rail = await client.get("/api/v1/rail/desk", headers=headers)
    assert runners.status_code == 401
    assert runners.json()["code"] == "LOGIN_REQUIRED"
    assert perps.status_code == 401
    assert perps.json()["code"] == "LOGIN_REQUIRED"
    assert rail.status_code == 401
    assert rail.json()["code"] == "LOGIN_REQUIRED"


@pytest.mark.asyncio
async def test_asset_symbol_still_requires_mfa_when_gate_on(totp_secret: str) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/assets/AAPL")
    assert res.status_code == 401
    assert res.json()["code"] == "LOGIN_REQUIRED"


@pytest.mark.asyncio
async def test_verify_totp_code_helper(totp_secret: str) -> None:
    code = pyotp.TOTP(totp_secret).now()
    assert verify_totp_code(code)
    assert not verify_totp_code("000000")


def test_mfa_token_bound_to_user() -> None:
    uid = uuid4()
    token = create_mfa_token(user_id=uid, grant_expires_at=datetime.now(UTC) + timedelta(days=1))
    assert decode_mfa_token(token, user_id=uid)
    assert not decode_mfa_token(token, user_id=uuid4())


def test_expired_mfa_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.site_gate.settings.secret_key", "test-secret")
    uid = uuid4()
    expire = datetime.now(UTC) - timedelta(hours=1)
    token = jwt.encode(
        {
            "typ": "site_mfa",
            "sub": str(uid),
            "exp": expire,
            "iat": expire - timedelta(hours=1),
        },
        "test-secret",
        algorithm=JWT_ALGORITHM,
    )
    assert not decode_mfa_token(token, user_id=uid)


@pytest.mark.asyncio
async def test_login_without_mfa_still_blocked(totp_secret: str) -> None:
    uid = uuid4()
    session = create_access_token(uid)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/v1/paper/summary?tick=false",
            cookies={"se_session": session},
        )
    assert res.status_code == 401
    assert res.json()["code"] == "MFA_REQUIRED"


@pytest.mark.asyncio
async def test_mfa_cookie_unlocks_data_path(totp_secret: str) -> None:
    uid = uuid4()
    session = create_access_token(uid)
    mfa = create_mfa_token(
        user_id=uid,
        grant_expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/v1/health",
            cookies={"se_session": session, MFA_COOKIE_NAME: mfa},
        )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_waitlist_requires_login_when_gate_on(totp_secret: str) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/auth/access/waitlist")
    assert res.status_code == 401
    assert res.json()["code"] == "LOGIN_REQUIRED"


@pytest.mark.asyncio
async def test_wallet_inbox_requires_mfa_when_logged_in(totp_secret: str) -> None:
    uid = uuid4()
    session = create_access_token(uid)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/v1/auth/access/wallets",
            cookies={"se_session": session},
        )
    assert res.status_code == 401
    assert res.json()["code"] == "MFA_REQUIRED"


async def _postgres_available() -> bool:
    engine = create_async_engine(
        settings.database_url, pool_pre_ping=True, poolclass=NullPool
    )
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_revoked_grant_is_rejected_even_with_mfa_cookie(
    totp_secret: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not await _postgres_available():
        pytest.skip("Postgres not available")

    engine = create_async_engine(
        settings.database_url, pool_pre_ping=True, poolclass=NullPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(db_session, "async_session_factory", factory)
    monkeypatch.setattr(db_session, "engine", engine)

    user_id = uuid4()
    async with factory() as session:
        session.add(
            User(
                id=user_id,
                email="granted@test.local",
                username="granted",
                password_hash=hash_password("grantedpass1"),
                email_verified_at=datetime.now(UTC),
            )
        )
        grant = AccessGrantModel(
            user_id=user_id,
            expires_at=datetime.now(UTC) + timedelta(days=30),
            notes="test",
        )
        session.add(grant)
        await session.commit()
        await session.refresh(grant)
        grant_id = grant.id

    session_tok = create_access_token(user_id)
    mfa = create_mfa_token(
        user_id=user_id,
        grant_expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    cookies = {"se_session": session_tok, MFA_COOKIE_NAME: mfa}
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            allowed = await client.get("/api/v1/paper/summary?tick=false", cookies=cookies)
            assert allowed.json().get("code") not in {
                "LOGIN_REQUIRED",
                "MFA_REQUIRED",
                "ACCESS_NOT_GRANTED",
            }

            async with factory() as session:
                row = await session.get(AccessGrantModel, grant_id)
                assert row is not None
                row.revoked_at = datetime.now(UTC)
                await session.commit()

            denied = await client.get("/api/v1/paper/summary?tick=false", cookies=cookies)
            assert denied.status_code == 403
            assert denied.json()["code"] == "ACCESS_NOT_GRANTED"
    finally:
        await engine.dispose()
