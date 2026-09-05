"""Password hashing and JWT helpers for social auth."""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import settings
from app.models.user import User

_DUMMY_PASSWORD_HASH: str | None = None

SESSION_COOKIE_NAME = "se_session"
JWT_ALGORITHM = "HS256"


@dataclass(frozen=True)
class SessionClaims:
    """Verified session JWT (user id + server-side version)."""

    user_id: uuid.UUID
    session_version: int


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Return True if password matches the stored hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def dummy_password_hash() -> str:
    """Valid bcrypt hash so unknown-email logins take the same time as real ones."""
    global _DUMMY_PASSWORD_HASH
    if _DUMMY_PASSWORD_HASH is None:
        _DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))
    return _DUMMY_PASSWORD_HASH


def bump_session_version(user: User) -> int:
    """Invalidate every JWT minted for this account (logout / password reset)."""
    next_v = int(user.session_version or 0) + 1
    user.session_version = next_v
    return next_v


def create_access_token(user_id: uuid.UUID, session_version: int = 0) -> str:
    """Issue a signed JWT for the given user id."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "typ": "session",
        "sub": str(user_id),
        "sv": int(session_version),
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def issue_session_token(user: User) -> str:
    """Mint a session JWT bound to the user's current session_version."""
    return create_access_token(user.id, int(user.session_version or 0))


def decode_session_claims(token: str) -> SessionClaims | None:
    """Decode a session JWT. Missing ``sv`` is treated as 0 (pre-version tokens)."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    if not sub or payload.get("typ", "session") != "session":
        return None
    try:
        user_id = uuid.UUID(str(sub))
        session_version = int(payload.get("sv", 0) or 0)
    except (ValueError, TypeError):
        return None
    return SessionClaims(user_id=user_id, session_version=session_version)


def decode_access_token(token: str) -> uuid.UUID | None:
    """Decode a JWT and return the user id, or None if invalid/expired."""
    claims = decode_session_claims(token)
    return None if claims is None else claims.user_id


def cookie_secure() -> bool:
    """Use Secure cookies in production (HTTPS)."""
    return settings.app_env.lower() == "production"
