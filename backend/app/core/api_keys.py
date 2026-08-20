"""API key generation, validation, and scope checks."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.config import settings
from app.models.access_grant import AccessGrantModel
from app.models.api_key import ApiKeyModel
from app.models.user import User

API_KEY_HEADER = "X-API-Key"
API_KEY_PREFIX = "se_live_"
REQUEST_STATE_ATTR = "api_key_auth"

ALL_READ_SCOPE = "*:read"

AVAILABLE_SCOPES: tuple[str, ...] = (
    ALL_READ_SCOPE,
    "expansion:read",
    "cortex:read",
    "assets:read",
    "runners:read",
    "perps:read",
    "futures:read",
    "paper:read",
    "opportunities:read",
    "setups:read",
    "equity-setups:read",
    "options-tape:read",
    "quotes:read",
    "alerts:read",
)

SCOPE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("/api/v1/expansion", "expansion:read"),
    ("/api/v1/cortex", "cortex:read"),
    ("/api/v1/assets", "assets:read"),
    ("/api/v1/runners", "runners:read"),
    ("/api/v1/perps", "perps:read"),
    ("/api/v1/futures", "futures:read"),
    ("/api/v1/paper", "paper:read"),
    ("/api/v1/opportunities", "opportunities:read"),
    ("/api/v1/setups", "setups:read"),
    ("/api/v1/equity-setups", "equity-setups:read"),
    ("/api/v1/options-tape", "options-tape:read"),
    ("/api/v1/quotes", "quotes:read"),
    ("/api/v1/alerts", "alerts:read"),
)


@dataclass(frozen=True)
class ApiKeyAuth:
    """Validated API key attached to request.state."""

    key_id: UUID
    user_id: UUID
    username: str
    scopes: tuple[str, ...]
    name: str


def normalize_scopes(raw: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        scope = item.strip()
        if not scope or scope in seen:
            continue
        if scope not in AVAILABLE_SCOPES:
            raise ValueError(f"Unknown scope: {scope}")
        seen.add(scope)
        out.append(scope)
    if not out:
        raise ValueError("At least one scope is required")
    return out


def hash_api_key(raw_key: str) -> str:
    material = f"{settings.secret_key}:{raw_key}".encode()
    return hashlib.sha256(material).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Return (full_key, key_prefix, key_hash)."""
    suffix = secrets.token_urlsafe(24)
    full_key = f"{API_KEY_PREFIX}{suffix}"
    key_prefix = full_key[:16]
    return full_key, key_prefix, hash_api_key(full_key)


def extract_api_key_from_request(request: Request) -> str | None:
    header = (request.headers.get(API_KEY_HEADER) or "").strip()
    if header.startswith(API_KEY_PREFIX):
        return header
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token.startswith(API_KEY_PREFIX):
            return token
    return None


def required_scope_for_path(path: str, method: str) -> str | None:
    """Map a request path to the scope an API key must hold (read-only Phase 1)."""
    if method.upper() not in {"GET", "HEAD"}:
        return None
    normalized = path.rstrip("/") or "/"
    for prefix, scope in SCOPE_PREFIXES:
        if normalized == prefix or normalized.startswith(f"{prefix}/"):
            return scope
    return None


def scope_allows(required: str | None, granted: tuple[str, ...]) -> bool:
    if required is None:
        return False
    if ALL_READ_SCOPE in granted:
        return True
    return required in granted


def get_api_key_auth(request: Request) -> ApiKeyAuth | None:
    return getattr(request.state, REQUEST_STATE_ATTR, None)


async def authenticate_api_key(
    request: Request,
    session: AsyncSession,
) -> tuple[ApiKeyAuth | None, str | None]:
    """Validate API key; return (auth, error_code)."""
    raw = extract_api_key_from_request(request)
    if not raw:
        return None, None
    if not raw.startswith(API_KEY_PREFIX) or len(raw) < len(API_KEY_PREFIX) + 8:
        return None, "INVALID_API_KEY"

    key_prefix = raw[:16]
    key_hash = hash_api_key(raw)
    now = datetime.now(UTC)

    row = (
        await session.execute(
            select(ApiKeyModel, User)
            .join(User, User.id == ApiKeyModel.user_id)
            .where(
                ApiKeyModel.key_prefix == key_prefix,
                ApiKeyModel.revoked_at.is_(None),
            )
        )
    ).first()
    if row is None:
        return None, "INVALID_API_KEY"

    api_key, user = row
    if not secrets.compare_digest(api_key.key_hash, key_hash):
        return None, "INVALID_API_KEY"
    if api_key.expires_at is not None:
        exp = api_key.expires_at if api_key.expires_at.tzinfo else api_key.expires_at.replace(tzinfo=UTC)
        if exp <= now:
            return None, "API_KEY_INACTIVE"

    if not settings.is_admin_username(user.username):
        grant = (
            await session.execute(
                select(AccessGrantModel)
                .where(
                    AccessGrantModel.user_id == user.id,
                    AccessGrantModel.revoked_at.is_(None),
                    AccessGrantModel.expires_at > now,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if grant is None:
            return None, "ACCESS_NOT_GRANTED"

    scopes = tuple(str(s) for s in (api_key.scopes or []))
    required = required_scope_for_path(request.url.path, request.method)
    if not scope_allows(required, scopes):
        return None, "INSUFFICIENT_SCOPE"

    api_key.last_used_at = now
    await session.commit()

    auth = ApiKeyAuth(
        key_id=api_key.id,
        user_id=user.id,
        username=user.username,
        scopes=scopes,
        name=api_key.name or "",
    )
    setattr(request.state, REQUEST_STATE_ATTR, auth)
    return auth, None
