"""Cortex API schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SpecialistOpinionSchema(BaseModel):
    specialist: str
    score: float | None = None
    direction: str | None = None
    factors: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SymbolContextSchema(BaseModel):
    symbol: str
    opinions: list[SpecialistOpinionSchema] = Field(default_factory=list)
    alert_level: str = "none"
    synthesis_notes: list[str] = Field(default_factory=list)
    prior_state: str | None = None
    expansion_summary: dict[str, Any] | None = None


class WorkingMemorySchema(BaseModel):
    tick_id: str
    as_of: datetime
    universe: list[str] = Field(default_factory=list)
    symbols: list[SymbolContextSchema] = Field(default_factory=list)
    global_opinions: list[SpecialistOpinionSchema] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    phase: str = "cortex_v2"
    primed: list[str] = Field(default_factory=list)
    triggering: list[str] = Field(default_factory=list)
    digest: str = ""


class CortexTickResponse(BaseModel):
    memory: WorkingMemorySchema
    persisted: bool = True


class EpisodicRecordSchema(BaseModel):
    tick_id: str
    as_of: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class CortexHistoryResponse(BaseModel):
    records: list[EpisodicRecordSchema] = Field(default_factory=list)
    count: int = 0


class SemanticStatSchema(BaseModel):
    metric: str
    signal: str
    score_bucket: int = -1
    sample_count: int = 0
    median_hours: float | None = None
    hit_rate: float | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class CortexSemanticResponse(BaseModel):
    stats: list[SemanticStatSchema] = Field(default_factory=list)
    lead_time_hours: float | None = None
    sample_count: int = 0


class CortexHealthSchema(BaseModel):
    last_tick_at: datetime | None = None
    ticks_recorded: int = 0
    healthy: bool = False
    backend: str = "memory"
    notes: list[str] = Field(default_factory=list)
