"""Attention router — which specialists fire each tick."""

from __future__ import annotations

from app.engines.expansion_engine.types import ExpansionState

# Specialist ids used by the cortex orchestrator.
EXPANSION_CLUSTER = "expansion"
REGIME = "regime"
DERIVATIVES = "derivatives"

_DEFAULT = (EXPANSION_CLUSTER, REGIME, DERIVATIVES)


def specialists_for_state(prior_state: ExpansionState | None) -> tuple[str, ...]:
    """Route specialists based on prior expansion state.

    Expansion cluster always runs (compression + squeeze + trigger inside).
    Regime + derivatives add context early; all three run every tick in v1.
    """
    del prior_state  # reserved for lighter DORMANT-only scans later
    return _DEFAULT


def should_run_global_macro() -> bool:
    """Global macro/regime tick — deferred until macro specialist exists."""
    return False
