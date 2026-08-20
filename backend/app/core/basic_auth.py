"""HTTP Basic Auth middleware for API lockdown."""

from __future__ import annotations

import base64
import secrets
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings
from app.core.api_keys import get_api_key_auth


def auth_enabled() -> bool:
    """Auth is on when a password is configured."""
    return bool(settings.auth_password.strip())


def is_public_path(path: str) -> bool:
    """Paths that never require Basic Auth."""
    normalized = path.rstrip("/") or "/"
    if normalized in {
        "/api/v1/health",
        "/api/v1/auth/gate/status",
        "/api/v1/auth/gate/verify",
        "/api/v1/auth/gate/logout",
    }:
        return True
    # Docs only in development when auth is otherwise on
    return settings.app_env == "development" and normalized in {
        "/docs",
        "/redoc",
        "/openapi.json",
    }


def credentials_valid(username: str, password: str) -> bool:
    """Constant-time compare against configured credentials."""
    expected_user = settings.auth_username.strip() or "signal"
    expected_pass = settings.auth_password
    return secrets.compare_digest(username, expected_user) and secrets.compare_digest(
        password, expected_pass
    )


def parse_basic_auth(header: str | None) -> tuple[str, str] | None:
    """Parse ``Authorization: Basic …`` into username/password."""
    if not header or not header.lower().startswith("basic "):
        return None
    try:
        raw = base64.b64decode(header[6:].strip()).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    if ":" not in raw:
        return None
    user, _, password = raw.partition(":")
    return user, password


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """Require HTTP Basic Auth when AUTH_PASSWORD is set."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)
        if get_api_key_auth(request) is not None:
            return await call_next(request)
        if not auth_enabled() or is_public_path(request.url.path):
            return await call_next(request)

        parsed = parse_basic_auth(request.headers.get("Authorization"))
        if parsed is None or not credentials_valid(parsed[0], parsed[1]):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"},
                headers={"WWW-Authenticate": 'Basic realm="Signal Engine"'},
            )
        return await call_next(request)
