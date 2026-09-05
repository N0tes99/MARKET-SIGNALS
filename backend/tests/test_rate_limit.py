"""In-process auth rate limiter."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.rate_limit import (
    check_rate_limit,
    client_ip,
    limit_heavy_compute,
    limit_login,
    limit_resend_verification,
    reset_rate_limits,
    run_serialized_heavy,
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
    assert client_ip(request) == "10.0.0.1"


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


def test_limit_resend_verification_is_independent_of_login() -> None:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(b"x-forwarded-for", b"203.0.113.50")],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
    }
    request = Request(scope)
    for _ in range(5):
        limit_resend_verification(request)
    with pytest.raises(HTTPException) as exc:
        limit_resend_verification(request)
    assert exc.value.status_code == 429
    limit_login(request, "other@example.com")


def test_limit_heavy_compute_caps_when_gate_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.site_gate.gate_enabled", lambda: True)
    monkeypatch.setattr(
        "app.core.site_gate.request_has_valid_cron_secret", lambda _req: False
    )

    def _req() -> Request:
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/runners/backtest",
            "raw_path": b"/api/v1/runners/backtest",
            "query_string": b"",
            "headers": [(b"x-forwarded-for", b"198.51.100.20")],
            "client": ("127.0.0.1", 1234),
            "server": ("test", 80),
        }
        return Request(scope)

    for _ in range(6):
        limit_heavy_compute(_req())
    with pytest.raises(HTTPException) as exc:
        limit_heavy_compute(_req())
    assert exc.value.status_code == 429


def test_limit_heavy_compute_skips_keep_warm_cron(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.site_gate.gate_enabled", lambda: True)
    monkeypatch.setattr(
        "app.core.site_gate.request_has_valid_cron_secret", lambda _req: True
    )
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/v1/assets",
        "raw_path": b"/api/v1/assets",
        "query_string": b"sync=true",
        "headers": [(b"x-cron-secret", b"keep-warm")],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
    }
    request = Request(scope)
    for _ in range(20):
        limit_heavy_compute(request)


def test_run_serialized_heavy_runs_one_at_a_time() -> None:
    seen: list[int] = []

    def _job(n: int) -> int:
        seen.append(n)
        return n

    assert run_serialized_heavy(_job, 1) == 1
    assert run_serialized_heavy(_job, 2) == 2
    assert seen == [1, 2]
