"""Simple thread-safe TTL cache with optional stale-while-revalidate."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock, Thread
from typing import TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


@dataclass
class _CacheEntry[T]:
    value: T
    expires_at: datetime


class TTLCache[T]:
    """In-memory cache with per-key expiry.

    Factories run outside the global lock so concurrent misses for different
    keys can fetch in parallel (critical for multi-symbol dashboards).
    """

    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = ttl_seconds
        self._entries: dict[str, _CacheEntry[T]] = {}
        self._lock = Lock()
        self._refreshing: set[str] = set()

    def get(self, key: str, *, allow_stale: bool = False) -> T | None:
        """Return a cached value if present.

        When ``allow_stale`` is False (default), expired entries are removed
        and treated as a miss. When True, expired values are still returned.
        """
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if datetime.now(UTC) >= entry.expires_at and not allow_stale:
                del self._entries[key]
                return None
            return entry.value

    def set(self, key: str, value: T) -> None:
        """Store a value until TTL elapses."""
        with self._lock:
            self._entries[key] = _CacheEntry(
                value=value,
                expires_at=datetime.now(UTC) + timedelta(seconds=self._ttl),
            )

    def clear(self) -> None:
        """Drop all cached entries."""
        with self._lock:
            self._entries.clear()
            self._refreshing.clear()

    def get_or_set(self, key: str, factory: Callable[[], T]) -> T:
        """Return cached value or compute, store, and return a new one."""
        cached = self.get(key)
        if cached is not None:
            return cached

        value = factory()

        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and datetime.now(UTC) < entry.expires_at:
                return entry.value
            self._entries[key] = _CacheEntry(
                value=value,
                expires_at=datetime.now(UTC) + timedelta(seconds=self._ttl),
            )
            return value

    def get_stale_while_revalidate(self, key: str, factory: Callable[[], T]) -> T:
        """Return cached data immediately; refresh in background when stale.

        - Fresh hit: return instantly.
        - Stale hit: return stale value instantly and refresh once in a daemon
          thread (single-flight per key).
        - Cold miss: block on ``factory`` (same as ``get_or_set``).
        """
        now = datetime.now(UTC)
        start_refresh = False
        stale_value: T | None = None

        with self._lock:
            entry = self._entries.get(key)
            if entry is not None:
                fresh = now < entry.expires_at
                stale_value = entry.value
                if fresh:
                    return stale_value
                if key not in self._refreshing:
                    self._refreshing.add(key)
                    start_refresh = True

        if stale_value is not None:
            if start_refresh:
                Thread(
                    target=self._background_refresh,
                    args=(key, factory),
                    daemon=True,
                    name=f"ttl-swr-{key}",
                ).start()
            return stale_value

        return self.get_or_set(key, factory)

    def _background_refresh(self, key: str, factory: Callable[[], T]) -> None:
        try:
            value = factory()
            self.set(key, value)
        except Exception:
            # Keep serving the prior stale value; next request can retry.
            logger.exception("Background cache refresh failed for key=%s", key)
        finally:
            with self._lock:
                self._refreshing.discard(key)
