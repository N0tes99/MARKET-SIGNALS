"""In-process sliding-window rate limits for auth endpoints.

Render free is a single web process, so this is enough to stop password
spraying and TOTP guessing without Redis. Keys are IP and/or email.
"""

from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

from app.config import settings

_LOCK = Lock()
_HITS: dict[str, deque[float]] = defaultdict(deque)


def reset_rate_limits() -> None:
    """Clear all buckets (tests)."""
    with _LOCK:
        _HITS.clear()


def client_ip(request: Request) -> str:
    """Best-effort client IP. Use the last XFF hop (the one the proxy added)."""
    parts = [
        hop.strip()
        for hop in (request.headers.get("x-forwarded-for") or "").split(",")
        if hop.strip()
    ]
    if parts:
        return parts[-1][:64]
    real = (request.headers.get("x-real-ip") or "").strip()
    if real:
        return real[:64]
    if request.client and request.client.host:
        return request.client.host[:64]
    return "unknown"


def check_rate_limit(key: str, *, limit: int, window_seconds: int) -> None:
    """Raise 429 when `key` exceeded `limit` hits in `window_seconds`."""
    if limit <= 0 or window_seconds <= 0:
        return
    now = monotonic()
    cutoff = now - window_seconds
    with _LOCK:
        bucket = _HITS[key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            retry = max(1, int(window_seconds - (now - bucket[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Try again later.",
                headers={"Retry-After": str(retry)},
            )
        bucket.append(now)


def limit_login(request: Request, email: str) -> None:
    """Cap login attempts per IP and per email."""
    window = settings.auth_rate_window_seconds
    ip = client_ip(request)
    check_rate_limit(
        f"login:ip:{ip}",
        limit=settings.auth_login_ip_limit,
        window_seconds=window,
    )
    normalized = email.lower().strip()
    if normalized:
        check_rate_limit(
            f"login:email:{normalized}",
            limit=settings.auth_login_email_limit,
            window_seconds=window,
        )


def limit_register(request: Request) -> None:
    check_rate_limit(
        f"register:ip:{client_ip(request)}",
        limit=settings.auth_register_ip_limit,
        window_seconds=settings.auth_rate_window_seconds,
    )


def limit_forgot_password(request: Request) -> None:
    check_rate_limit(
        f"forgot:ip:{client_ip(request)}",
        limit=settings.auth_forgot_ip_limit,
        window_seconds=settings.auth_rate_window_seconds,
    )


def limit_resend_verification(request: Request) -> None:
    check_rate_limit(
        f"resend:ip:{client_ip(request)}",
        limit=settings.auth_forgot_ip_limit,
        window_seconds=settings.auth_rate_window_seconds,
    )


def limit_wallet(request: Request, action: str) -> None:
    check_rate_limit(
        f"wallet:{action}:ip:{client_ip(request)}",
        limit=settings.auth_wallet_ip_limit,
        window_seconds=settings.auth_rate_window_seconds,
    )


def limit_totp(request: Request, user_id: str) -> None:
    """Cap authenticator guesses per user and per IP."""
    window = settings.auth_rate_window_seconds
    check_rate_limit(
        f"totp:user:{user_id}",
        limit=settings.auth_totp_limit,
        window_seconds=window,
    )
    check_rate_limit(
        f"totp:ip:{client_ip(request)}",
        limit=settings.auth_totp_limit,
        window_seconds=window,
    )


def limit_chart_analysis(request: Request, user_id: str) -> None:
    """Cap vision screenshot analysis per user and IP (token-expensive)."""
    window = settings.auth_rate_window_seconds
    check_rate_limit(
        f"chart:user:{user_id}",
        limit=8,
        window_seconds=window,
    )
    check_rate_limit(
        f"chart:ip:{client_ip(request)}",
        limit=20,
        window_seconds=window,
    )


def limit_expensive(request: Request) -> None:
    """Cap unauthenticated-looking compute ticks when the site is locked down."""
    from app.core.basic_auth import auth_enabled
    from app.core.site_gate import gate_enabled

    if not auth_enabled() and not gate_enabled():
        return
    check_rate_limit(
        f"expensive:ip:{client_ip(request)}",
        limit=12,
        window_seconds=60,
    )
