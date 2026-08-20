"""Cortex orchestrator — one heartbeat, shared working memory."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

from app.cortex.attention import specialists_for_state
from app.cortex.specialists import (
    build_specialist_engines,
    collect_derivatives_opinion,
    collect_regime_opinion,
)
from app.cortex.synthesis import (
    alert_level_for,
    expansion_to_opinion,
    synthesize_symbol_notes,
)
from app.cortex.types import SymbolContext, WorkingMemory
from app.engines.expansion_engine.config import BENCHMARK_UNIVERSE, default_expansion_config
from app.engines.expansion_engine.scanner import ExpansionScanner
from app.engines.expansion_engine.types import ExpansionState
from app.market_data.service import MarketDataService
from app.memory.episodic.store import EpisodicStore, InMemoryEpisodicStore

logger = logging.getLogger(__name__)


class CortexOrchestrator:
    """Runs specialist engines into a shared blackboard each tick."""

    def __init__(
        self,
        *,
        market_data: MarketDataService | None = None,
        expansion_scanner: ExpansionScanner | None = None,
        episodic: EpisodicStore | None = None,
    ) -> None:
        self._market = market_data or MarketDataService()
        self._expansion = expansion_scanner or ExpansionScanner(market_data=self._market)
        self._regime, self._derivatives = build_specialist_engines(self._market)
        self._episodic = episodic or InMemoryEpisodicStore()
        self._prior_states: dict[str, ExpansionState] = {}
        self._last_memory: WorkingMemory | None = None

    @property
    def last_memory(self) -> WorkingMemory | None:
        return self._last_memory

    @property
    def episodic(self) -> EpisodicStore:
        return self._episodic

    def tick(
        self,
        *,
        symbols: tuple[str, ...] | None = None,
        persist: bool = True,
    ) -> WorkingMemory:
        """Execute one cortex cycle across the universe."""
        universe = symbols or default_expansion_config().universe or BENCHMARK_UNIVERSE
        tick_id = uuid4().hex[:12]
        as_of = datetime.now(UTC)
        notes: list[str] = []
        symbol_contexts: dict[str, SymbolContext] = {}

        for sym in universe:
            normalized = sym.upper()
            prior = self._prior_states.get(normalized)
            active = specialists_for_state(prior)
            opinions = []

            expansion = None
            if "expansion" in active:
                try:
                    expansion = self._expansion.scan_symbol(normalized, as_of=as_of)
                except Exception:
                    logger.exception("Cortex expansion cluster failed for %s", normalized)
                if expansion is not None:
                    opinions.append(expansion_to_opinion(expansion))

            if "regime" in active:
                opinions.append(collect_regime_opinion(self._regime, normalized))

            if "derivatives" in active:
                opinions.append(collect_derivatives_opinion(self._derivatives, normalized))

            ctx = SymbolContext(
                symbol=normalized,
                opinions=opinions,
                expansion=expansion,
                prior_state=prior,
                alert_level=alert_level_for(expansion),
            )
            ctx.synthesis_notes = synthesize_symbol_notes(ctx)
            symbol_contexts[normalized] = ctx

            if expansion is not None:
                self._prior_states[normalized] = expansion.state

        primed = [s for s, c in symbol_contexts.items() if c.alert_level == "primed"]
        triggering = [
            s
            for s, c in symbol_contexts.items()
            if c.alert_level in {"trigger", "expansion"}
        ]
        if primed:
            notes.append(f"PRIMED: {', '.join(primed)}")
        if triggering:
            notes.append(f"TRIGGER/EXPAND: {', '.join(triggering)}")
        if not primed and not triggering:
            notes.append("No primed/trigger alerts this tick")

        memory = WorkingMemory(
            tick_id=tick_id,
            as_of=as_of,
            universe=universe,
            symbols=symbol_contexts,
            notes=notes,
            phase="cortex_v1",
        )

        self._last_memory = memory
        if persist:
            self._episodic.append(memory)
        return memory

    def digest(self) -> str:
        """One-line human summary for morning brief / logs."""
        mem = self._last_memory
        if mem is None:
            return "Cortex: no tick yet"
        parts = [f"Cortex tick {mem.tick_id}"]
        alerts = mem.alert_symbols()
        if alerts:
            bits = [f"{sym}={level}" for sym, level in alerts]
            parts.append("alerts: " + ", ".join(bits))
        else:
            parts.append("alerts: none")
        parts.append(f"universe: {len(mem.universe)}")
        return " | ".join(parts)
