"""Configurable weights and thresholds for Surface 4 Runner Detection."""

from __future__ import annotations

from dataclasses import dataclass, field

# Seed universe for testing / benchmarking — not recommendations.
DEFAULT_SEED_UNIVERSE: tuple[str, ...] = (
    "NBIS",
    "CRWV",
    "SMCI",
    "IREN",
    "AAOI",
    "CRDO",
    "ALAB",
    "POET",
    "INDI",
    "COHR",
    "LITE",
    "MXL",
    "AIP",
    "ICHR",
    "COHU",
    "UCTT",
    "AMPX",
    "PLPC",
    "PWR",
    "CEG",
    "VRT",
    "CLS",
)


@dataclass(frozen=True)
class MarketCapBucket:
    """Asymmetry market-cap band (USD millions)."""

    label: str
    max_mcap_usd: float | None  # None = open-ended
    asymmetry_hint: float


DEFAULT_MARKET_CAP_BUCKETS: tuple[MarketCapBucket, ...] = (
    MarketCapBucket("extreme", 500_000_000.0, 90.0),
    MarketCapBucket("primary", 2_000_000_000.0, 80.0),
    MarketCapBucket("secondary", 10_000_000_000.0, 60.0),
    MarketCapBucket("lower", None, 35.0),
)


@dataclass
class AlertThresholds:
    """Alert gates — do not fire constantly."""

    # High-priority
    high_runner_min: float = 85.0
    high_fundamental_min: float = 70.0
    high_catalyst_min: float = 70.0
    high_structure_min: float = 75.0

    # Standard
    standard_runner_min: float = 75.0
    standard_fundamental_min: float = 65.0
    standard_discovery_gap_min: float = 60.0
    max_risk_for_alert: float = 70.0

    # Early (pre-breakout)
    early_fundamental_min: float = 75.0
    early_discovery_gap_min: float = 70.0
    early_structure_min: float = 45.0
    early_structure_max: float = 70.0


@dataclass
class RunnerWeights:
    """Modifier weights applied after the multiplicative core."""

    discovery_gap: float = 0.15
    theme_bottleneck: float = 0.10
    institutional_accum: float = 0.08
    short_squeeze: float = 0.05


@dataclass
class StageThresholds:
    """Score thresholds for Stage 0–7 classification."""

    fundamental_inflection: float = 65.0
    structure_accumulation: float = 55.0
    catalyst: float = 65.0
    ignition_structure: float = 70.0
    discovery_gap_low: float = 45.0  # gap closing → discovery
    momentum_structure: float = 80.0
    extended_structure: float = 88.0
    extended_discovery_gap_max: float = 35.0


@dataclass
class RunnerConfig:
    """All tunable Runner Detection knobs."""

    seed_universe: tuple[str, ...] = DEFAULT_SEED_UNIVERSE
    market_cap_buckets: tuple[MarketCapBucket, ...] = DEFAULT_MARKET_CAP_BUCKETS
    alerts: AlertThresholds = field(default_factory=AlertThresholds)
    weights: RunnerWeights = field(default_factory=RunnerWeights)
    stages: StageThresholds = field(default_factory=StageThresholds)
    # Multiplicative core: map each 0–100 score into this band before multiply
    core_scale_low: float = 0.25
    core_scale_high: float = 1.25
    scan_cache_ttl_seconds: float = 120.0
    # Tape-only (no fundamentals) cannot print a high Runner Score
    structure_only_cap: float = 62.0


RUNNER_PHASE = "4_lists"


def default_runner_config() -> RunnerConfig:
    """Return default config (future: load from env/YAML)."""
    return RunnerConfig()
