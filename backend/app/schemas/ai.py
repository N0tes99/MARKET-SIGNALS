"""AI explanation response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class AIExplanationVariantSchema(BaseModel):
    """One reasoning source (desk synthesizer or Groq)."""

    summary: str
    factors: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    source: str
    generated_at: datetime


class AIExplanationSchema(BaseModel):
    """Human-readable AI analysis for an asset."""

    symbol: str
    summary: str = Field(..., description="1-2 sentence overview")
    confidence: float = Field(..., ge=0, le=100)
    factors: list[str] = Field(default_factory=list, description="Supporting evidence bullets")
    conflicts: list[str] = Field(default_factory=list, description="Opposing signals flagged")
    source: str = Field(..., description="local or groq")
    generated_at: datetime
    local: AIExplanationVariantSchema | None = Field(
        default=None,
        description="Desk synthesizer reading when compare=true",
    )
    groq: AIExplanationVariantSchema | None = Field(
        default=None,
        description="Groq reading when compare=true and the key is set",
    )
    groq_status: str | None = Field(
        default=None,
        description="ok, unavailable, or failed — set when compare=true",
    )
