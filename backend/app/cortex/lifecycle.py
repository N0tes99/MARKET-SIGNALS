"""Cortex lifecycle — health and degrade handling (Phase B scaffold)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CortexHealth:
    """Snapshot of cortex operational status."""

    last_tick_at: datetime | None
    ticks_recorded: int
    healthy: bool
    notes: list[str]


def assess_health(*, last_tick_at: datetime | None, ticks_recorded: int) -> CortexHealth:
    """Placeholder health check until Postgres episodic + alerts ship."""
    notes: list[str] = []
    if last_tick_at is None:
        notes.append("No cortex tick yet")
    return CortexHealth(
        last_tick_at=last_tick_at,
        ticks_recorded=ticks_recorded,
        healthy=last_tick_at is not None,
        notes=notes,
    )
