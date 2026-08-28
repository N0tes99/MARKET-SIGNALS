"""Surface 4 Runner Detection API schemas."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

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


class RunnerScoresSchema(BaseModel):
    """Score breakdown — opportunity and risk stay separate."""

    fundamental: float = Field(..., ge=0, le=100)
    catalyst: float = Field(..., ge=0, le=100)
    structure: float = Field(..., ge=0, le=100)
    asymmetry: float = Field(..., ge=0, le=100)
    discovery_gap: float = Field(..., ge=0, le=100)
    theme_bottleneck: float = Field(..., ge=0, le=100)
    institutional_accum: float = Field(..., ge=0, le=100)
    short_squeeze_potential: float = Field(..., ge=0, le=100)
    runner_score: float = Field(..., ge=0, le=100)
    risk_score: float = Field(..., ge=0, le=100)
    penalties: float = 0.0


class RunnerCandidateSchema(BaseModel):
    """Explainable runner radar candidate."""

    id: str
    symbol: str
    instrument_type: Literal["runner"] = "runner"
    stage: RunnerStage
    signal_type: RunnerSignalType
    watchlist: WatchlistBucket
    alert_gate: AlertGate = "none"
    scores: RunnerScoresSchema
    factors: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0, le=100)
    data_quality: DataQuality = "missing"
    as_of: datetime
    phase: str = "5_leadtime"
    qualities: dict[str, DataQuality] = Field(default_factory=dict)
    ret_20d_pct: float | None = None
    relative_volume: float | None = None
    rs_benchmark: str | None = None
    rs_pct: float | None = None


class RunnerFeedResponse(BaseModel):
    """Ranked runner feed across seed universe."""

    candidates: list[RunnerCandidateSchema] = Field(default_factory=list)
    scanned_at: datetime
    symbols_scanned: int = 0
    fundamentals_filled: int = 0
    fundamentals_missing: int = 0
    watchlist: WatchlistBucket | None = None
    min_runner_score: float = 0.0
    stage: RunnerStage | None = None


class RunnerDetailResponse(BaseModel):
    """Single-symbol runner detail."""

    candidate: RunnerCandidateSchema
    scanned_at: datetime


class RunnerListsResponse(BaseModel):
    """EARLY / IGNITION / RUNNING buckets."""

    early: list[RunnerCandidateSchema] = Field(default_factory=list)
    ignition: list[RunnerCandidateSchema] = Field(default_factory=list)
    running: list[RunnerCandidateSchema] = Field(default_factory=list)
    scanned_at: datetime
    symbols_scanned: int = 0
    fundamentals_filled: int = 0
    fundamentals_missing: int = 0


class RunnerConfigMetaResponse(BaseModel):
    """Public thresholds (no secrets)."""

    seed_universe: list[str]
    alert_high_runner_min: float
    alert_standard_runner_min: float
    alert_early_fundamental_min: float
    alert_early_discovery_gap_min: float
    phase: str = "5_leadtime"


class RunnerBacktestSnapshotSchema(BaseModel):
    """Classify at T-N using only bars on or before that date."""

    offset_days: int | None = None
    as_of: date
    last_close: float | None = None
    stage: RunnerStage
    watchlist: WatchlistBucket
    runner_score: float
    structure: float
    fundamentals_available: bool = False


class RunnerBacktestCaseSchema(BaseModel):
    """One study path — multiples are outcome labels, not features."""

    symbol: str
    bars: int
    error: str | None = None
    trough_date: date | None = None
    hit_2x: bool = False
    hit_5x: bool = False
    hit_10x: bool = False
    date_2x: date | None = None
    date_5x: date | None = None
    date_10x: date | None = None
    days_to_2x: int | None = None
    days_to_5x: int | None = None
    days_to_10x: int | None = None
    first_early: date | None = None
    first_ignition: date | None = None
    first_running: date | None = None
    lead_days_to_2x: int | None = None
    late_for_2x: bool = False
    max_dd_after_early_pct: float | None = None
    snapshots: list[RunnerBacktestSnapshotSchema] = Field(default_factory=list)


class RunnerBacktestMetricsSchema(BaseModel):
    """Precision / recall / FPR / lead time on the study set."""

    n_cases: int = 0
    n_2x: int = 0
    n_5x: int = 0
    n_10x: int = 0
    n_signaled_early: int = 0
    true_positives_2x: int = 0
    false_positives_2x: int = 0
    false_negatives_2x: int = 0
    precision_2x: float | None = None
    recall_2x: float | None = None
    false_positive_rate_2x: float | None = None
    true_positives_5x: int = 0
    false_positives_5x: int = 0
    false_negatives_5x: int = 0
    precision_5x: float | None = None
    recall_5x: float | None = None
    false_positive_rate_5x: float | None = None
    median_lead_days_2x: float | None = None
    median_days_to_2x: float | None = None
    median_days_to_5x: float | None = None
    median_max_dd_pct: float | None = None


class RunnerBacktestResponse(BaseModel):
    """Phase 5 v0 lead-time study. Structure tape only unless dated snapshots."""

    phase: str
    mode: str
    generated_at: datetime
    look_ahead: str
    symbols: list[str] = Field(default_factory=list)
    cases: list[RunnerBacktestCaseSchema] = Field(default_factory=list)
    metrics: RunnerBacktestMetricsSchema
