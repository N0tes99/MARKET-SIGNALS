"""Admin is a harder auth principal than a granted desk user."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.config import settings
from app.core.basic_auth import is_public_path
from app.core.rate_limit import limit_totp, reset_rate_limits
from app.core.security import (
    JWT_ALGORITHM,
    issue_session_token,
    session_expire_minutes_for,
)
from app.core.site_gate import (
    create_mfa_token,
    is_access_public_path,
    mfa_expire_minutes_for,
)
from app.models.user import User


def _user(*, username: str) -> User:
    return User(
        id=uuid4(),
        email=f"{username.lower()}@test.local",
        username=username,
        password_hash="not-a-real-hash",
        created_at=datetime.now(UTC),
    )


def _jwt_ttl_seconds(token: str) -> int:
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[JWT_ALGORITHM],
        options={"require": ["exp", "iat"]},
    )

    def _ts(value: object) -> int:
        if isinstance(value, datetime):
            return int(value.timestamp())
        return int(value)

    return _ts(payload["exp"]) - _ts(payload["iat"])


def test_admin_session_expires_in_hours_not_weeks() -> None:
    admin = _user(username="Admin")
    other = _user(username="builder")
    assert session_expire_minutes_for(admin) == settings.admin_session_expire_minutes
    assert session_expire_minutes_for(other) == settings.access_token_expire_minutes
    admin_ttl = _jwt_ttl_seconds(issue_session_token(admin))
    other_ttl = _jwt_ttl_seconds(issue_session_token(other))
    assert 7 * 3600 < admin_ttl < 9 * 3600
    assert 13 * 24 * 3600 < other_ttl < 15 * 24 * 3600


def test_admin_mfa_cookie_lasts_about_an_hour() -> None:
    assert mfa_expire_minutes_for(is_admin=True) == settings.admin_mfa_expire_minutes
    assert mfa_expire_minutes_for(is_admin=False) == settings.site_gate_expire_hours * 60
    uid = uuid4()
    admin_ttl = _jwt_ttl_seconds(
        create_mfa_token(
            user_id=uid,
            grant_expires_at=None,
            expire_minutes=mfa_expire_minutes_for(is_admin=True),
        )
    )
    desk_ttl = _jwt_ttl_seconds(
        create_mfa_token(user_id=uid, grant_expires_at=None)
    )
    assert 50 * 60 < admin_ttl < 70 * 60
    assert 11 * 3600 < desk_ttl < 13 * 3600


def test_totp_verify_requires_basic_auth_when_password_set() -> None:
    assert is_public_path("/api/v1/health") is True
    assert is_public_path("/api/v1/auth/gate/status") is True
    assert is_public_path("/api/v1/auth/gate/verify") is False


def test_change_password_is_not_an_access_public_path() -> None:
    assert is_access_public_path("/api/v1/auth/change-password") is False
    assert is_access_public_path("/api/v1/auth/forgot-password") is True


def test_limit_totp_is_stricter_for_admin() -> None:
    reset_rate_limits()

    def _req() -> Request:
        return Request(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": "/api/v1/auth/gate/verify",
                "raw_path": b"/api/v1/auth/gate/verify",
                "query_string": b"",
                "headers": [(b"x-forwarded-for", b"198.51.100.8")],
                "client": ("127.0.0.1", 1234),
                "server": ("test", 80),
            }
        )

    for _ in range(settings.admin_totp_limit):
        limit_totp(_req(), "admin-user", admin=True)
    with pytest.raises(HTTPException) as exc:
        limit_totp(_req(), "admin-user", admin=True)
    assert exc.value.status_code == 429
    reset_rate_limits()
    for _ in range(settings.auth_totp_limit):
        limit_totp(_req(), "desk-user", admin=False)
    with pytest.raises(HTTPException) as exc:
        limit_totp(_req(), "desk-user", admin=False)
    assert exc.value.status_code == 429


def test_api_keys_are_blocked_for_admin_accounts() -> None:
    root = Path(__file__).resolve().parents[1]
    routes = (root / "app" / "api" / "routes" / "api_keys.py").read_text(encoding="utf-8")
    core = (root / "app" / "core" / "api_keys.py").read_text(encoding="utf-8")
    auth = (root / "app" / "api" / "routes" / "auth.py").read_text(encoding="utf-8")
    assert "API keys cannot be issued for admin accounts" in routes
    assert "is_admin_username(user.username)" in core
    assert 'if user is None or settings.is_admin_username(user.username):' in auth
    assert "/change-password" in auth
    password_page = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "app"
        / "settings"
        / "password"
        / "page.tsx"
    ).read_text(encoding="utf-8")
    assert "Admin accounts cannot reset by email" in password_page
