"""In-memory semantic stats (tests and when Postgres is unset)."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from typing import Protocol

from app.memory.semantic.types import SemanticStat


class SemanticStore(Protocol):
    def upsert(self, stat: SemanticStat) -> None: ...

    def get(
        self, metric: str, signal: str, *, score_bucket: int = -1
    ) -> SemanticStat | None: ...

    def all_stats(self) -> list[SemanticStat]: ...


def _key(metric: str, signal: str, score_bucket: int) -> tuple[str, str, int]:
    return (metric, signal, score_bucket)


class InMemorySemanticStore:
    """Process-local semantic stats."""

    backend = "memory"

    def __init__(self) -> None:
        self._stats: dict[tuple[str, str, int], SemanticStat] = {}
        self._lock = Lock()

    def upsert(self, stat: SemanticStat) -> None:
        stamped = SemanticStat(
            metric=stat.metric,
            signal=stat.signal,
            score_bucket=stat.score_bucket,
            sample_count=stat.sample_count,
            median_hours=stat.median_hours,
            hit_rate=stat.hit_rate,
            payload=dict(stat.payload),
            updated_at=stat.updated_at or datetime.now(UTC),
        )
        with self._lock:
            self._stats[_key(stat.metric, stat.signal, stat.score_bucket)] = stamped

    def get(self, metric: str, signal: str, *, score_bucket: int = -1) -> SemanticStat | None:
        return self._stats.get(_key(metric, signal, score_bucket))

    def all_stats(self) -> list[SemanticStat]:
        return list(self._stats.values())
