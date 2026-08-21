"""Attention router — which specialists fire each tick."""

from __future__ import annotations

from app.engines.expansion_engine.types import ExpansionState

# Specialist ids used by the cortex orchestrator.
EXPANSION_CLUSTER = "expansion"
REGIME = "regime"
DERIVATIVES = "derivatives"
CVD = "cvd"
NEWS = "news"

_DEFAULT = (EXPANSION_CLUSTER, REGIME, DERIVATIVES, CVD, NEWS)


def specialists_for_state(prior_state: ExpansionState | None) -> tuple[str, ...]:
    """Route specialists based on prior expansion state.

    Expansion cluster always runs (compression + squeeze + trigger inside).
    CVD (order-flow proxy), news/calendar, regime, and derivatives run every tick.
    """
    del prior_state  # reserved for lighter DORMANT-only scans later
    return _DEFAULT


def should_run_global_macro() -> bool:
    """Global macro snapshot once per tick (not per symbol)."""
    return True
