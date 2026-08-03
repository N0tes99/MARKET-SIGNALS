"""TTL cache tests."""

import time

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
