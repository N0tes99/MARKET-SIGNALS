"""Expansion radar API schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ExpansionStateSchema = Literal["dormant", "primed", "triggering", "expanding"]
DirectionBiasSchema = Literal["up", "down", "neutral"]
ConfidenceSchema = Literal["low", "medium", "high"]
SetupLevelSchema = Literal["low", "medium", "high"]


class ScoreContributorSchema(BaseModel):
    label: str
    points: float
    detail: str = ""


class SqueezeFuelLevelSchema(BaseModel):
    pct_move: float
    label: str


class CompressionSchema(BaseModel):
    score: float = Field(..., ge=0, le=100)
    atr_percentile: float | None = None
    bb_width_percentile: float | None = None
    range_compression_pct: float | None = None
    volume_compression_pct: float | None = None
    factors: list[str] = Field(default_factory=list)


class SqueezeFuelSchema(BaseModel):
    score: float = Field(..., ge=0, le=100)
    direction: DirectionBiasSchema
    levels: list[SqueezeFuelLevelSchema] = Field(default_factory=list)
    factors: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


class TriggerSchema(BaseModel):
    active: bool
    direction: DirectionBiasSchema
    volume_ratio: float | None = None
    breakout_level: float | None = None
    factors: list[str] = Field(default_factory=list)


class ExpansionCandidateSchema(BaseModel):
    id: str
    symbol: str
    state: ExpansionStateSchema
    direction_bias: DirectionBiasSchema
    up_score: float = Field(..., ge=0, le=100)
    down_score: float = Field(..., ge=0, le=100)
    net_score: float = Field(..., ge=0, le=100)
    confidence: ConfidenceSchema
    setup_level: SetupLevelSchema
    trigger_active: bool
    horizon: str
    invalidation: str
    key_trigger: str
    compression: CompressionSchema
    squeeze: SqueezeFuelSchema
    trigger: TriggerSchema
    contributors: list[ScoreContributorSchema] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    factors: list[str] = Field(default_factory=list)
    price: float | None = None
    funding_bps: float | None = None
    oi_change_pct: float | None = None
    mom_12h_pct: float | None = None
    as_of: datetime


class ExpansionFeedResponse(BaseModel):
    candidates: list[ExpansionCandidateSchema] = Field(default_factory=list)
    primed: list[ExpansionCandidateSchema] = Field(default_factory=list)
    triggering: list[ExpansionCandidateSchema] = Field(default_factory=list)
    expanding: list[ExpansionCandidateSchema] = Field(default_factory=list)
    scanned_at: datetime
    symbols_scanned: int = 0
    universe: list[str] = Field(default_factory=list)
    phase: str = "perp_v2_universe"


class ReplayEventSchema(BaseModel):
    symbol: str
    max_move_pct: float
    primed_hours_before_move: int | None = None
    v2_hours_after_move_start: int | None = None
    primed_before_v2: bool | None = None


class ExpansionReplayResponse(BaseModel):
    events: list[ReplayEventSchema] = Field(default_factory=list)
    benchmark_symbols: list[str] = Field(default_factory=list)
    scanned_at: datetime
