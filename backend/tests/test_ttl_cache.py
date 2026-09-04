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


def test_cache_meta_reports_freshness_and_age() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=60.0)
    cache.set("k", "v")
    value, fresh, refreshing, age = cache.meta("k")
    assert value == "v"
    assert fresh is True
    assert refreshing is False
    assert age is not None
    assert age < 1.0

    missing, miss_fresh, miss_refreshing, miss_age = cache.meta("missing")
    assert missing is None
    assert miss_fresh is False
    assert miss_refreshing is False
    assert miss_age is None


def test_max_entries_evicts_oldest() -> None:
    cache: TTLCache[int] = TTLCache(ttl_seconds=60.0, max_entries=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3
