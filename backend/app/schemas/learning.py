"""Learning and similarity API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SimilarMatchSchema(BaseModel):
    """Historically similar signal match."""

    id: UUID
    symbol: str
    timestamp: datetime
    confidence: float
    trade_grade: str
    trade_state: str
    similarity: float = Field(..., description="Cosine similarity 0-100")
    category_scores: dict[str, float]


class SimilarityResponseSchema(BaseModel):
    """Similarity search results for an asset."""

    symbol: str
    matches: list[SimilarMatchSchema]
    history_count: int


class SignalRecordSchema(BaseModel):
    """Stored signal record."""

    id: UUID
    symbol: str
    timestamp: datetime
    confidence: float
    trade_grade: str
    trade_state: str
    execution_signal: str
    opportunity_score: float
    category_scores: dict[str, float]
