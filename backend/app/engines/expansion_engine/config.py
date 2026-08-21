"""Configurable thresholds for the expansion engine MVP."""

from __future__ import annotations

from dataclasses import dataclass

from app.market_data.perp_universe import PERP_V2_UNIVERSE

# Live expansion + cortex scan universe (aligned with paper v2).
EXPANSION_UNIVERSE: tuple[str, ...] = PERP_V2_UNIVERSE

EXPANSION_PHASE = "perp_v2_universe"


@dataclass(frozen=True)
class ExpansionConfig:
    """Knobs for compression, squeeze, trigger, and scoring."""

    universe: tuple[str, ...] = EXPANSION_UNIVERSE

    # Compression
    compression_lookback: int = 20
    compression_min_bars: int = 30
    compression_primedd_atr_pctile: float = 20.0
    compression_high_atr_pctile: float = 10.0
    compression_primedd_score: float = 75.0
    compression_high_score: float = 85.0

    # Trigger (15m primary, 5m confirm)
    trigger_timeframe: str = "15m"
    trigger_confirm_timeframe: str = "5m"
    trigger_volume_lookback: int = 20
    trigger_volume_mult: float = 1.5
    trigger_range_lookback: int = 12

    # Squeeze fuel
    squeeze_funding_soft_bps: float = 3.0
    squeeze_funding_extreme_bps: float = 8.0
    squeeze_oi_build_pct: float = 3.0
    squeeze_oi_unwind_pct: float = -3.0

    # State thresholds
    primed_min_compression: float = 75.0
    expanding_min_momentum_pct: float = 1.5

    # Scoring weights (configurable — sum need not be 1.0; composer normalizes)
    weight_compression: float = 0.25
    weight_squeeze: float = 0.25
    weight_trigger: float = 0.20
    weight_momentum: float = 0.15
    weight_derivatives: float = 0.15

    # Alerts
    watch_net_score: float = 60.0
    primed_net_score: float = 75.0
    trigger_net_score: float = 80.0


DEFAULT_EXPANSION_CONFIG = ExpansionConfig()


def expansion_config_to_dict(cfg: ExpansionConfig) -> dict[str, object]:
    """JSON-friendly knobs (universe as a list)."""
    return {
        "universe": list(cfg.universe),
        "compression_lookback": cfg.compression_lookback,
        "compression_min_bars": cfg.compression_min_bars,
        "compression_primedd_atr_pctile": cfg.compression_primedd_atr_pctile,
        "compression_high_atr_pctile": cfg.compression_high_atr_pctile,
        "compression_primedd_score": cfg.compression_primedd_score,
        "compression_high_score": cfg.compression_high_score,
        "trigger_timeframe": cfg.trigger_timeframe,
        "trigger_confirm_timeframe": cfg.trigger_confirm_timeframe,
        "trigger_volume_lookback": cfg.trigger_volume_lookback,
        "trigger_volume_mult": cfg.trigger_volume_mult,
        "trigger_range_lookback": cfg.trigger_range_lookback,
        "squeeze_funding_soft_bps": cfg.squeeze_funding_soft_bps,
        "squeeze_funding_extreme_bps": cfg.squeeze_funding_extreme_bps,
        "squeeze_oi_build_pct": cfg.squeeze_oi_build_pct,
        "squeeze_oi_unwind_pct": cfg.squeeze_oi_unwind_pct,
        "primed_min_compression": cfg.primed_min_compression,
        "expanding_min_momentum_pct": cfg.expanding_min_momentum_pct,
        "weight_compression": cfg.weight_compression,
        "weight_squeeze": cfg.weight_squeeze,
        "weight_trigger": cfg.weight_trigger,
        "weight_momentum": cfg.weight_momentum,
        "weight_derivatives": cfg.weight_derivatives,
        "watch_net_score": cfg.watch_net_score,
        "primed_net_score": cfg.primed_net_score,
        "trigger_net_score": cfg.trigger_net_score,
    }


def expansion_config_from_dict(data: dict[str, object] | None) -> ExpansionConfig:
    """Overlay a knobs dict on file defaults; unknown keys ignored."""
    if not data:
        return DEFAULT_EXPANSION_CONFIG
    kwargs: dict[str, object] = {}
    allowed = set(expansion_config_to_dict(DEFAULT_EXPANSION_CONFIG))
    for key, value in data.items():
        if key not in allowed:
            continue
        if key == "universe":
            if isinstance(value, (list, tuple)) and value:
                kwargs[key] = tuple(str(s).upper() for s in value)
            continue
        kwargs[key] = value
    try:
        return ExpansionConfig(**kwargs)  # type: ignore[arg-type]
    except TypeError:
        return DEFAULT_EXPANSION_CONFIG


def file_expansion_config() -> ExpansionConfig:
    """Compiled-in defaults (ignores Postgres)."""
    return DEFAULT_EXPANSION_CONFIG


def default_expansion_config() -> ExpansionConfig:
    """Live knobs: Postgres policy when migrated, else file defaults."""
    from app.memory.procedural.config_store import load_expansion_config

    return load_expansion_config()
