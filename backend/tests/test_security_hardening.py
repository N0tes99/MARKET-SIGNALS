"""Auth and leak hardening: reserved admins, MFA on admin APIs, XFF last hop."""

from __future__ import annotations

from pathlib import Path

from starlette.requests import Request

from app.core.rate_limit import client_ip
from app.core.site_gate import is_access_public_path

_ROOT = Path(__file__).resolve().parents[2]
_UNLOCK = _ROOT / "frontend" / "app" / "unlock" / "page.tsx"
_SAFE_NEXT = _ROOT / "frontend" / "lib" / "safe-next.ts"
_PROXY = _ROOT / "frontend" / "app" / "api" / "backend" / "[...path]" / "route.ts"


def test_admin_access_api_is_not_a_public_path() -> None:
    assert is_access_public_path("/api/v1/auth/access/waitlist") is False
    assert is_access_public_path("/api/v1/auth/access/wallets") is False
    assert is_access_public_path("/api/v1/auth/access/grants") is False
    assert is_access_public_path("/api/v1/auth/login") is True


def test_client_ip_uses_last_forwarded_hop() -> None:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(b"x-forwarded-for", b"203.0.113.9, 10.0.0.4")],
        "client": ("10.0.0.4", 1234),
        "server": ("test", 80),
    }
    request = Request(scope)
    assert client_ip(request) == "10.0.0.4"


def test_unlock_uses_safe_next_path() -> None:
    text = _UNLOCK.read_text(encoding="utf-8")
    assert 'from "@/lib/safe-next"' in text
    assert 'safeNextPath(searchParams?.get("next"), "/")' in text
    assert 'nextPath.startsWith("/")' not in text
    helper = _SAFE_NEXT.read_text(encoding="utf-8")
    assert 'trimmed.startsWith("//")' in helper
    assert 'trimmed.includes("\\\\")' in helper


def test_proxy_forwards_only_netlify_client_ip() -> None:
    text = _PROXY.read_text(encoding="utf-8")
    assert "x-nf-client-connection-ip" in text
    assert 'headers.set("x-forwarded-for", clientIp)' in text
    assert 'request.headers.get("x-real-ip")' not in text
    assert 'request.headers.get("x-forwarded-for")' not in text
    assert 'request.headers.get("x-cron-secret")' not in text
