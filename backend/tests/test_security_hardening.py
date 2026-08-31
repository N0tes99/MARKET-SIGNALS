"""Auth and leak hardening: reserved admins, MFA on admin APIs, XFF last hop."""

from __future__ import annotations

from starlette.requests import Request

from app.core.rate_limit import client_ip
from app.core.site_gate import is_access_public_path


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
