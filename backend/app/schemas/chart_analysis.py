"""Schemas for screenshot / chart analysis."""

from datetime import datetime

from pydantic import BaseModel, Field


class ChartReadingSchema(BaseModel):
    """What is visible on the uploaded screenshot."""

    symbol: str | None = None
    asset_class: str | None = None
    timeframe: str | None = None
    chart_type: str | None = None
    last_price: float | None = None
    trend: str = "unclear"
    structure: str = ""
    key_levels: list[str] = Field(default_factory=list)
    indicators_visible: list[str] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)
    image_quality: str = "partial"


class PositionIdeaSchema(BaseModel):
    """A possible setup read from the chart. Analysis, not an order."""

    bias: str = Field(..., description="long, short, or no_trade")
    setup_name: str
    thesis: str
    entry_zone: str | None = None
    invalidation: str | None = None
    targets: list[str] = Field(default_factory=list)
    risk_notes: str = ""
    execution_hint: str = Field(..., description="WAIT, WATCH, or EXECUTE")
    confidence: float = Field(..., ge=0, le=100)
    chart_derived: bool = True


class EngineGroundingSchema(BaseModel):
    """Live desk evidence for a tracked symbol, if the chart named one."""

    symbol: str
    tracked: bool
    trade_state: str
    trade_grade: str
    execution_signal: str
    opportunity_score: float
    summary: str
    alignment: str = Field(..., description="agrees, conflicts, or incomplete")
    alignment_notes: list[str] = Field(default_factory=list)
    asset_path: str | None = None


class ChartAnalysisSchema(BaseModel):
    """Full screenshot analysis response."""

    reading: ChartReadingSchema
    thesis: str
    positions: list[PositionIdeaSchema]
    conflicts: list[str] = Field(default_factory=list)
    engine_grounding: EngineGroundingSchema | None = None
    source: str
    disclaimer: str
    generated_at: datetime


class ChartAnalysisStatusSchema(BaseModel):
    """Whether vision is configured, or desk-engine fallback will run."""

    vision: bool
    source: str = Field(..., description="openai, groq, gemini, or local")
    hint: str
