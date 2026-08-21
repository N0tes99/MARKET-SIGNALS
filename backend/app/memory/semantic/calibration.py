"""Score bucket → hit rate calibration."""

from __future__ import annotations

from app.memory.semantic.consolidator import LEAD_SIGNAL
from app.memory.semantic.store import SemanticStore


def calibration_hit_rate(
    score_bucket: int,
    *,
    store: SemanticStore | None = None,
    events: list[dict] | None = None,
) -> float | None:
    """Return hit rate for a 10-point score bucket from semantic memory."""
    del events
    if store is None:
        return None
    stat = store.get("calibration", LEAD_SIGNAL, score_bucket=score_bucket)
    return stat.hit_rate if stat is not None else None
