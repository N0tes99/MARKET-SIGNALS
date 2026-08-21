"""Cortex lifecycle — health and degrade handling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class CortexHealth:
    """Snapshot of cortex operational status."""

    last_tick_at: datetime | None
    ticks_recorded: int
    healthy: bool
    backend: str
    notes: list[str]


def assess_health(
    *,
    last_tick_at: datetime | None,
    ticks_recorded: int,
    backend: str = "memory",
    stale_after: timedelta = timedelta(minutes=10),
) -> CortexHealth:
    """Healthy when a tick exists and is newer than ``stale_after``."""
    notes: list[str] = []
    now = datetime.now(UTC)
    healthy = last_tick_at is not None
    if last_tick_at is None:
        notes.append("No cortex tick yet")
    else:
        age = now - last_tick_at
        if age > stale_after:
            healthy = False
            notes.append(f"Last tick {int(age.total_seconds() // 60)}m ago (stale)")
        else:
            notes.append("Tick is fresh")
    if ticks_recorded == 0:
        notes.append("Episodic store is empty")
    notes.append(f"backend={backend}")
    return CortexHealth(
        last_tick_at=last_tick_at,
        ticks_recorded=ticks_recorded,
        healthy=healthy,
        backend=backend,
        notes=notes,
    )
