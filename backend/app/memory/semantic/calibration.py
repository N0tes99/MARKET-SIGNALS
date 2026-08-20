"""Score bucket → hit rate calibration (Phase B scaffold)."""

from __future__ import annotations


def calibration_hit_rate(score_bucket: int, *, events: list[dict] | None = None) -> float | None:
    """Return hit rate for a 10-point score bucket once episodic outcomes exist."""
    del score_bucket, events
    return None
