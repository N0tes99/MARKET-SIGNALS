"""Expansion policy versions (Phase B scaffold)."""

from __future__ import annotations

from app.engines.expansion_engine.config import default_expansion_config


def active_expansion_policy() -> dict[str, object]:
    """Return the live expansion knobs; later versioned in Postgres."""
    cfg = default_expansion_config()
    return {
        "universe": list(cfg.universe),
        "primed_min_compression": cfg.primed_min_compression,
        "trigger_volume_mult": cfg.trigger_volume_mult,
        "watch_net_score": cfg.watch_net_score,
        "primed_net_score": cfg.primed_net_score,
        "trigger_net_score": cfg.trigger_net_score,
    }
