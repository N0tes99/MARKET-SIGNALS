"""AI explanation response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class AIExplanationSchema(BaseModel):
    """Human-readable AI analysis for an asset."""

    symbol: str
    summary: str = Field(..., description="1-2 sentence overview")
    confidence: float = Field(..., ge=0, le=100)
    factors: list[str] = Field(default_factory=list, description="Supporting evidence bullets")
    conflicts: list[str] = Field(default_factory=list, description="Opposing signals flagged")
    source: str = Field(..., description="local, openai, or gemini")
    generated_at: datetime
