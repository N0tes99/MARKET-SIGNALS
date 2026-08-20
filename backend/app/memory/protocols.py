"""Memory protocols — episodic, semantic, procedural (Phase B)."""

from __future__ import annotations

from typing import Any, Protocol

from app.cortex.types import WorkingMemory
from app.memory.episodic.types import EpisodicRecord


class EpisodicMemory(Protocol):
    def append(self, memory: WorkingMemory) -> EpisodicRecord: ...

    def latest(self) -> EpisodicRecord | None: ...

    def history(self, limit: int = 20) -> list[EpisodicRecord]: ...


class SemanticMemory(Protocol):
    """Lead-time stats and calibration buckets — not wired yet."""

    def lead_time_median_hours(self, signal: str) -> float | None: ...

    def calibration_hit_rate(self, score_bucket: int) -> float | None: ...


class ProceduralMemory(Protocol):
    """Versioned expansion policies and weights."""

    def active_policy(self) -> dict[str, Any]: ...
