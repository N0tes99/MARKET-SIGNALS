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
_COMPOSE = _ROOT / "docker-compose.yml"
_MIDDLEWARE = _ROOT / "frontend" / "middleware.ts"
_NEXT_CONFIG = _ROOT / "frontend" / "next.config.ts"
_LAYOUT = _ROOT / "frontend" / "app" / "layout.tsx"
_ADMIN_KEYS = _ROOT / "frontend" / "app" / "admin" / "api-access" / "page.tsx"
_SOCIAL_CARD = _ROOT / "frontend" / "components" / "social-post-card.tsx"


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


def test_compose_ports_bind_localhost_only() -> None:
    text = _COMPOSE.read_text(encoding="utf-8")
    assert "127.0.0.1:5432:5432" in text
    assert "127.0.0.1:6379:6379" in text
    assert "127.0.0.1:8000:8000" in text
    assert "127.0.0.1:3000:3000" in text
    assert '"5432:5432"' not in text
    assert '"6379:6379"' not in text


def test_csp_uses_script_nonce_not_static_unsafe_inline() -> None:
    middleware = _MIDDLEWARE.read_text(encoding="utf-8")
    config = _NEXT_CONFIG.read_text(encoding="utf-8")
    layout = _LAYOUT.read_text(encoding="utf-8")
    assert "nonce-${nonce}" in middleware
    assert "'strict-dynamic'" in middleware
    assert 'NODE_ENV === "production"' in middleware
    assert "Content-Security-Policy" not in config
    assert "x-nonce" in middleware
    assert "await headers()" in layout
    assert "dangerouslySetInnerHTML" not in _SOCIAL_CARD.read_text(encoding="utf-8")
    assert "{post.body}" in _SOCIAL_CARD.read_text(encoding="utf-8")


def test_api_key_admin_copy_warns_ttl() -> None:
    text = _ADMIN_KEYS.read_text(encoding="utf-8")
    assert "90 days" in text
    assert "Treat a leaked" in text
