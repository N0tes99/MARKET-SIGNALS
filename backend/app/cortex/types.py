"""Cortex blackboard types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from app.engines.expansion_engine.types import ExpansionCandidate, ExpansionState

AlertLevel = Literal["none", "watch", "primed", "trigger", "expansion"]


@dataclass(frozen=True)
class SpecialistOpinion:
    """One specialist's view for a symbol or global context."""

    specialist: str
    score: float | None
    direction: str | None
    factors: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SymbolContext:
    """Shared blackboard slice for one asset."""

    symbol: str
    opinions: list[SpecialistOpinion] = field(default_factory=list)
    expansion: ExpansionCandidate | None = None
    prior_state: ExpansionState | None = None
    alert_level: AlertLevel = "none"
    synthesis_notes: list[str] = field(default_factory=list)


@dataclass
class WorkingMemory:
    """Current cortex cycle — what all specialists know right now."""

    tick_id: str
    as_of: datetime
    universe: tuple[str, ...]
    symbols: dict[str, SymbolContext] = field(default_factory=dict)
    global_opinions: list[SpecialistOpinion] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    phase: str = "cortex_v1"

    def primed_symbols(self) -> list[str]:
        return [
            sym
            for sym, ctx in self.symbols.items()
            if ctx.expansion and ctx.expansion.state == ExpansionState.PRIMED
        ]

    def triggering_symbols(self) -> list[str]:
        return [
            sym
            for sym, ctx in self.symbols.items()
            if ctx.expansion
            and ctx.expansion.state in {ExpansionState.TRIGGERING, ExpansionState.EXPANDING}
        ]

    def alert_symbols(self) -> list[tuple[str, AlertLevel]]:
        return [
            (sym, ctx.alert_level)
            for sym, ctx in self.symbols.items()
            if ctx.alert_level != "none"
        ]
