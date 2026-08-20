"""Configurable thresholds for the expansion engine MVP."""

from __future__ import annotations

from dataclasses import dataclass

# Benchmark-first universe (BTC/SOL/SUI pump miss). Full V2 list when validated.
BENCHMARK_UNIVERSE: tuple[str, ...] = ("BTC", "SOL", "SUI")

EXPANSION_PHASE = "mvp_benchmark"


@dataclass(frozen=True)
class ExpansionConfig:
    """Knobs for compression, squeeze, trigger, and scoring."""

    universe: tuple[str, ...] = BENCHMARK_UNIVERSE

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


def default_expansion_config() -> ExpansionConfig:
    return DEFAULT_EXPANSION_CONFIG
