"""Product-level market-data freshness gate (not TTL SWR).

Tracks last successful provider fetches and consecutive empty/error responses.
When data cannot be refreshed past a threshold, surfaces a degraded-mode flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock

from app.config import settings


@dataclass(frozen=True)
class FreshnessSnapshot:
    """Current freshness state for a symbol (or global aggregate)."""

    degraded: bool
    reason: str | None
    age_seconds: float | None
    consecutive_failures: int
    last_success_at: datetime | None


class DataFreshnessTracker:
    """Thread-safe per-symbol freshness tracker for OHLCV/ticker fetches."""

    def __init__(
        self,
        *,
        stale_seconds: float | None = None,
        failure_threshold: int | None = None,
    ) -> None:
        self._stale_seconds = (
            float(settings.market_data_stale_seconds)
            if stale_seconds is None
            else stale_seconds
        )
        self._failure_threshold = (
            int(settings.market_data_failure_threshold)
            if failure_threshold is None
            else failure_threshold
        )
        self._lock = Lock()
        self._last_success: dict[str, datetime] = {}
        self._last_observed: dict[str, datetime] = {}
        self._failures: dict[str, int] = {}

    def reset(self) -> None:
        """Clear all tracked state (tests)."""
        with self._lock:
            self._last_success.clear()
            self._last_observed.clear()
            self._failures.clear()

    def record_success(
        self,
        symbol: str,
        *,
        observed_at: datetime | None = None,
        fetched_at: datetime | None = None,
    ) -> None:
        """Record a successful OHLCV/ticker fetch for ``symbol``."""
        key = symbol.upper()
        now = fetched_at or datetime.now(UTC)
        obs = observed_at
        if obs is not None and obs.tzinfo is None:
            obs = obs.replace(tzinfo=UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        with self._lock:
            self._last_success[key] = now
            self._failures[key] = 0
            if obs is not None:
                self._last_observed[key] = obs

    def record_failure(self, symbol: str) -> None:
        """Record an empty response or provider error for ``symbol``."""
        key = symbol.upper()
        with self._lock:
            self._failures[key] = self._failures.get(key, 0) + 1

    def status(self, symbol: str, *, now: datetime | None = None) -> FreshnessSnapshot:
        """Evaluate degraded mode for a single symbol."""
        key = symbol.upper()
        clock = now or datetime.now(UTC)
        if clock.tzinfo is None:
            clock = clock.replace(tzinfo=UTC)

        with self._lock:
            last_success = self._last_success.get(key)
            last_observed = self._last_observed.get(key)
            failures = self._failures.get(key, 0)

        return self._evaluate(last_success, last_observed, failures, clock)

    def any_degraded(self, symbols: list[str] | None = None) -> bool:
        """True if any tracked (or listed) symbol is degraded."""
        clock = datetime.now(UTC)
        with self._lock:
            keys = list(symbols) if symbols is not None else list(
                set(self._last_success) | set(self._failures) | set(self._last_observed)
            )
            states = [
                (
                    self._last_success.get(k.upper()),
                    self._last_observed.get(k.upper()),
                    self._failures.get(k.upper(), 0),
                )
                for k in keys
            ]
        return any(
            self._evaluate(success, observed, failures, clock).degraded
            for success, observed, failures in states
        )

    def _evaluate(
        self,
        last_success: datetime | None,
        last_observed: datetime | None,
        failures: int,
        clock: datetime,
    ) -> FreshnessSnapshot:
        age_seconds: float | None = None
        if last_success is not None:
            age_seconds = max(0.0, (clock - last_success).total_seconds())
        elif last_observed is not None:
            obs = last_observed if last_observed.tzinfo else last_observed.replace(tzinfo=UTC)
            age_seconds = max(0.0, (clock - obs).total_seconds())

        if failures >= self._failure_threshold:
            return FreshnessSnapshot(
                degraded=True,
                reason="provider_errors",
                age_seconds=age_seconds,
                consecutive_failures=failures,
                last_success_at=last_success,
            )

        if age_seconds is not None and age_seconds > self._stale_seconds:
            return FreshnessSnapshot(
                degraded=True,
                reason="stale_data",
                age_seconds=age_seconds,
                consecutive_failures=failures,
                last_success_at=last_success,
            )

        return FreshnessSnapshot(
            degraded=False,
            reason=None,
            age_seconds=age_seconds,
            consecutive_failures=failures,
            last_success_at=last_success,
        )


# Process-wide tracker used by MarketDataService and API mappers.
freshness_tracker = DataFreshnessTracker()
