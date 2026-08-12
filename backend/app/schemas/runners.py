"""Surface 4 Runner Detection API schemas."""

from datetime import datetime
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
    scores: RunnerScoresSchema
    factors: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0, le=100)
    data_quality: DataQuality = "missing"
    as_of: datetime
    phase: str = "1_stub"


class RunnerFeedResponse(BaseModel):
    """Ranked runner feed across seed universe."""

    candidates: list[RunnerCandidateSchema] = Field(default_factory=list)
    scanned_at: datetime
    symbols_scanned: int = 0
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


class RunnerConfigMetaResponse(BaseModel):
    """Public thresholds (no secrets)."""

    seed_universe: list[str]
    alert_high_runner_min: float
    alert_standard_runner_min: float
    alert_early_fundamental_min: float
    alert_early_discovery_gap_min: float
    phase: str = "1_stub"
