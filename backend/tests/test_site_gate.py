"""Access gate: login → grant → shared TOTP."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pyotp
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import JWT_ALGORITHM, create_access_token
from app.core.site_gate import MFA_COOKIE_NAME, create_mfa_token, decode_mfa_token, verify_totp_code
from app.main import app


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
async def test_assets_list_mfa_session_still_works_when_gate_on(totp_secret: str) -> None:
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
    assert res.status_code != 401
    assert res.json().get("code") not in {"LOGIN_REQUIRED", "MFA_REQUIRED"}


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
async def test_waitlist_skips_mfa_but_still_requires_admin(totp_secret: str) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/auth/access/waitlist")
    assert res.status_code == 401
    body = res.json()
    assert body.get("code") not in {"LOGIN_REQUIRED", "MFA_REQUIRED"}


@pytest.mark.asyncio
async def test_wallet_inbox_skips_mfa_but_still_requires_admin(totp_secret: str) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/auth/access/wallets")
    assert res.status_code == 401
    assert res.json().get("code") not in {"LOGIN_REQUIRED", "MFA_REQUIRED"}
