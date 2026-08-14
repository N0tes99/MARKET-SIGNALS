"""Shared keep-alive httpx clients reuse connections without changing payloads."""

from app.utils.http_client import reset_shared_clients, shared_client


def test_shared_client_reuses_same_instance() -> None:
    reset_shared_clients()
    a = shared_client(timeout=5.0, name="test-kraken")
    b = shared_client(timeout=5.0, name="test-kraken")
    assert a is b


def test_shared_client_splits_by_timeout_and_name() -> None:
    reset_shared_clients()
    a = shared_client(timeout=5.0, name="test-a")
    b = shared_client(timeout=2.0, name="test-a")
    c = shared_client(timeout=5.0, name="test-b")
    assert a is not b
    assert a is not c


def test_reset_shared_clients_closes_pool() -> None:
    reset_shared_clients()
    first = shared_client(timeout=5.0, name="test-reset")
    reset_shared_clients()
    second = shared_client(timeout=5.0, name="test-reset")
    assert first is not second
    assert first.is_closed
