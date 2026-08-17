"""In-process auth rate limiter."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.rate_limit import (
    check_rate_limit,
    client_ip,
    limit_login,
    reset_rate_limits,
)


@pytest.fixture(autouse=True)
def _reset_limits() -> None:
    reset_rate_limits()
    yield
    reset_rate_limits()


def test_check_rate_limit_allows_then_blocks() -> None:
    for _ in range(3):
        check_rate_limit("unit:key", limit=3, window_seconds=60)
    with pytest.raises(HTTPException) as exc:
        check_rate_limit("unit:key", limit=3, window_seconds=60)
    assert exc.value.status_code == 429
    assert exc.value.headers is not None
    assert "Retry-After" in exc.value.headers


def test_buckets_are_independent() -> None:
    for _ in range(2):
        check_rate_limit("a", limit=2, window_seconds=60)
    check_rate_limit("b", limit=2, window_seconds=60)


def test_client_ip_prefers_forwarded_for() -> None:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(b"x-forwarded-for", b"203.0.113.9, 10.0.0.1")],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
    }
    request = Request(scope)
    assert client_ip(request) == "203.0.113.9"


def test_limit_login_blocks_same_email_across_ips() -> None:
    def _req(ip: str) -> Request:
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [(b"x-forwarded-for", ip.encode())],
            "client": ("127.0.0.1", 1234),
            "server": ("test", 80),
        }
        return Request(scope)

    email = "admin@example.com"
    for i in range(8):
        limit_login(_req(f"198.51.100.{i}"), email)
    with pytest.raises(HTTPException) as exc:
        limit_login(_req("198.51.100.99"), email)
    assert exc.value.status_code == 429
