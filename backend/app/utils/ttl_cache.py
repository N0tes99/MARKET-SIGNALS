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

    def __init__(self, ttl_seconds: float, max_entries: int | None = None) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
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
            self._evict_unlocked()

    def _evict_unlocked(self) -> None:
        """Drop expired, then oldest, entries when over max_entries. Caller holds lock."""
        if self._max_entries is None or len(self._entries) <= self._max_entries:
            return
        now = datetime.now(UTC)
        expired = [key for key, entry in self._entries.items() if now >= entry.expires_at]
        for key in expired:
            if key in self._refreshing:
                continue
            del self._entries[key]
            if len(self._entries) <= self._max_entries:
                return
        overflow = len(self._entries) - self._max_entries
        if overflow <= 0:
            return
        oldest = sorted(self._entries.items(), key=lambda item: item[1].expires_at)
        for key, _entry in oldest[:overflow]:
            if key in self._refreshing:
                continue
            del self._entries[key]

    def seed_stale(self, key: str, value: T) -> None:
        """Store a value already expired so the next SWR hit refreshes in background."""
        with self._lock:
            self._entries[key] = _CacheEntry(
                value=value,
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
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
            self._evict_unlocked()
            return value

    def meta(self, key: str) -> tuple[T | None, bool, bool, float | None]:
        """Return (value, is_fresh, is_refreshing, age_seconds).

        ``age_seconds`` is time since the entry was written (approx), or None
        when the key is missing.
        """
        now = datetime.now(UTC)
        with self._lock:
            entry = self._entries.get(key)
            refreshing = key in self._refreshing
            if entry is None:
                return None, False, refreshing, None
            fresh = now < entry.expires_at
            written_at = entry.expires_at - timedelta(seconds=self._ttl)
            age = max(0.0, (now - written_at).total_seconds())
            return entry.value, fresh, refreshing, age

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
