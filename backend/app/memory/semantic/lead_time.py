"""Lead-time statistics from episodic expansion events."""

from __future__ import annotations

from app.memory.semantic.consolidator import LEAD_SIGNAL
from app.memory.semantic.store import SemanticStore


def median_lead_time_hours(
    signal: str = LEAD_SIGNAL,
    *,
    store: SemanticStore | None = None,
    events: list[dict] | None = None,
) -> float | None:
    """Median hours from primed to trigger/expansion."""
    del events
    if store is None:
        return None
    stat = store.get("lead_time", signal)
    return stat.median_hours if stat is not None else None
