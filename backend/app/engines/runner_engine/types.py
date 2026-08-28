"""Surface 4 Runner Detection types — opportunity radar, not EXECUTE orders."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

RunnerStage = Literal[
    "dormant",
    "fundamental_inflection",
    "early_accumulation",
    "catalyst",
    "ignition",
    "discovery",
    "momentum",
    "extended",
]

RunnerSignalType = Literal[
    "early_runner",
    "accumulation",
    "ignition",
    "confirmed_runner",
    "extended_runner",
    "runner_failure",
    "none",
]

WatchlistBucket = Literal["early", "ignition", "running", "none"]
AlertGate = Literal["high", "early", "none"]
DataQuality = Literal["good", "degraded", "missing"]

STAGE_ORDER: tuple[RunnerStage, ...] = (
    "dormant",
    "fundamental_inflection",
    "early_accumulation",
    "catalyst",
    "ignition",
    "discovery",
    "momentum",
    "extended",
)


@dataclass
class RunnerTapeSnapshot:
    """Structure-tape extras for the preview Radar UI (None = unknown)."""

    ret_20d_pct: float | None = None
    relative_volume: float | None = None
    rs_benchmark: str | None = None
    rs_pct: float | None = None
    structure_score: float | None = None


@dataclass
class DimensionScore:
    """One scored dimension with explainability."""

    name: str
    score: float
    confidence: float = 1.0
    factors: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    data_quality: DataQuality = "good"


@dataclass
class RunnerScores:
    """Full Runner Score breakdown — opportunity and risk stay separate."""

    fundamental: float = 50.0
    catalyst: float = 50.0
    structure: float = 50.0
    asymmetry: float = 50.0
    discovery_gap: float = 50.0
    theme_bottleneck: float = 50.0
    institutional_accum: float = 50.0
    short_squeeze_potential: float = 50.0
    runner_score: float = 0.0
    risk_score: float = 50.0
    penalties: float = 0.0


@dataclass
class RunnerCandidate:
    """Explainable runner radar candidate (WATCHLIST / ALERT only in M10)."""

    id: str
    symbol: str
    stage: RunnerStage
    signal_type: RunnerSignalType
    watchlist: WatchlistBucket
    scores: RunnerScores
    alert_gate: AlertGate = "none"
    factors: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    confidence: float = 0.0
    data_quality: DataQuality = "missing"
    as_of: datetime = field(default_factory=lambda: datetime.now(UTC))
    instrument_type: Literal["runner"] = "runner"
    phase: str = "5_leadtime"
    qualities: dict[str, DataQuality] = field(default_factory=dict)
    tape: RunnerTapeSnapshot = field(default_factory=RunnerTapeSnapshot)
