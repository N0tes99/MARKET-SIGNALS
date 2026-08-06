"""TTL cache tests."""

import time
from threading import Event

from app.utils.ttl_cache import TTLCache


def test_ttl_cache_returns_fresh_value() -> None:
    cache: TTLCache[int] = TTLCache(ttl_seconds=60.0)
    calls = 0

    def factory() -> int:
        nonlocal calls
        calls += 1
        return calls

    assert cache.get_or_set("key", factory) == 1
    assert cache.get_or_set("key", factory) == 1
    assert calls == 1


def test_ttl_cache_expires() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=0.05)
    assert cache.get_or_set("key", lambda: "first") == "first"
    time.sleep(0.06)
    assert cache.get_or_set("key", lambda: "second") == "second"


def test_stale_while_revalidate_returns_stale_immediately() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=0.08)
    assert cache.get_stale_while_revalidate("k", lambda: "v1") == "v1"
    time.sleep(0.1)

    started = Event()
    done = Event()

    def slow_factory() -> str:
        started.set()
        time.sleep(0.05)
        done.set()
        return "v2"

    # Must return stale value without waiting for the refresh to finish.
    assert cache.get_stale_while_revalidate("k", slow_factory) == "v1"
    assert started.wait(timeout=1.0)
    assert done.wait(timeout=1.0)
    time.sleep(0.02)
    assert cache.get("k") == "v2"


def test_stale_while_revalidate_cold_miss_blocks() -> None:
    cache: TTLCache[int] = TTLCache(ttl_seconds=60.0)
    assert cache.get_stale_while_revalidate("cold", lambda: 42) == 42


def test_seed_stale_returns_immediately_and_refreshes() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=60.0)
    cache.seed_stale("k", "disk")
    # Seeded value is readable as stale; do not call get(allow_stale=False)
    # first — that deletes expired entries and forces a cold miss.
    assert cache.get("k", allow_stale=True) == "disk"

    started = Event()
    done = Event()

    def slow_factory() -> str:
        started.set()
        time.sleep(0.08)
        done.set()
        return "fresh"

    assert cache.get_stale_while_revalidate("k", slow_factory) == "disk"
    assert started.wait(timeout=1.0)
    assert done.wait(timeout=1.0)
    time.sleep(0.05)
    assert cache.get("k") == "fresh"
