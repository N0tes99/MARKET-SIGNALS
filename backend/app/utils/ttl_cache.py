"""Simple thread-safe TTL cache."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Callable, TypeVar

T = TypeVar("T")


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

    def get(self, key: str) -> T | None:
        """Return a cached value if present and not expired."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if datetime.now(UTC) >= entry.expires_at:
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
