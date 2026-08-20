"""Episodic memory store — ring buffer of cortex ticks."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from app.cortex.types import WorkingMemory
from app.engines.expansion_engine.types import ExpansionState
from app.memory.episodic.types import EpisodicRecord


class EpisodicStore(Protocol):
    def append(self, memory: WorkingMemory) -> EpisodicRecord: ...

    def latest(self) -> EpisodicRecord | None: ...

    def history(self, limit: int = 20) -> list[EpisodicRecord]: ...


def _serialize(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, StrEnum):
        return obj.value
    if isinstance(obj, datetime):
        return obj.isoformat()
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _serialize(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(v) for v in obj]
    if isinstance(obj, ExpansionState):
        return obj.value
    return obj


def serialize_working_memory(memory: WorkingMemory) -> dict[str, Any]:
    """JSON-safe snapshot for episodic storage."""
    symbols: dict[str, Any] = {}
    for sym, ctx in memory.symbols.items():
        expansion = ctx.expansion
        symbols[sym] = {
            "symbol": ctx.symbol,
            "prior_state": ctx.prior_state.value if ctx.prior_state else None,
            "alert_level": ctx.alert_level,
            "synthesis_notes": list(ctx.synthesis_notes),
            "opinions": [_serialize(o) for o in ctx.opinions],
            "expansion": _serialize(expansion) if expansion else None,
        }

    return {
        "tick_id": memory.tick_id,
        "as_of": memory.as_of.isoformat(),
        "universe": list(memory.universe),
        "symbols": symbols,
        "global_opinions": [_serialize(o) for o in memory.global_opinions],
        "notes": list(memory.notes),
        "phase": memory.phase,
        "primed": memory.primed_symbols(),
        "triggering": memory.triggering_symbols(),
    }


class InMemoryEpisodicStore:
    """Ring buffer of recent cortex ticks (dev + MVP)."""

    def __init__(self, max_records: int = 100) -> None:
        self._records: deque[EpisodicRecord] = deque(maxlen=max_records)

    def append(self, memory: WorkingMemory) -> EpisodicRecord:
        record = EpisodicRecord(
            tick_id=memory.tick_id,
            as_of=memory.as_of,
            payload=serialize_working_memory(memory),
        )
        self._records.append(record)
        return record

    def latest(self) -> EpisodicRecord | None:
        if not self._records:
            return None
        return self._records[-1]

    def history(self, limit: int = 20) -> list[EpisodicRecord]:
        n = max(1, min(limit, len(self._records)))
        return list(self._records)[-n:]
