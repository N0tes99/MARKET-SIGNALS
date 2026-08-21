"""Semantic memory types — lead time and calibration buckets."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class SemanticStat:
    """One consolidated metric from episodic cortex history."""

    metric: str
    signal: str
    score_bucket: int = -1
    sample_count: int = 0
    median_hours: float | None = None
    hit_rate: float | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime | None = None
