"""Evidence-related Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EvidenceItemSchema(BaseModel):
    """Single evidence factor in an API response."""

    source: str = Field(..., description="Engine that produced this evidence")
    category: str = Field(..., description="Scoring category")
    score: float = Field(..., ge=0, le=100, description="Category score 0–100")
    weight: float = Field(..., description="Category weight in total confidence")
    description: str = Field(..., description="Human-readable evidence description")
    confidence: float = Field(
        default=1.0,
        description="Item confidence multiplier (scoring clamps to 0.5–1.5)",
    )


class EvidenceBundleSchema(BaseModel):
    """Full evidence bundle for an asset."""

    id: UUID = Field(..., description="Unique bundle identifier")
    symbol: str = Field(..., description="Asset ticker symbol")
    timeframe: str = Field(..., description="Analysis timeframe")
    total_confidence: float = Field(..., ge=0, le=100, description="Weighted confidence")
    items: list[EvidenceItemSchema] = Field(..., description="Contributing evidence factors")
    timestamp: datetime = Field(..., description="When evidence was accumulated")
    regime: str | None = Field(default=None, description="Market regime label")
    regime_confidence: float | None = Field(
        default=None,
        description="Regime classification confidence 0–100",
    )


class EvidenceSnapshotSchema(EvidenceBundleSchema):
    """Persisted evidence snapshot with storage metadata."""

    created_at: datetime = Field(..., description="When snapshot was persisted")
