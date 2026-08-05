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
    outcome: str | None = None
    realized_return_pct: float | None = None


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
    expected_value: float | None = None
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    outcome: str | None = None
    realized_return_pct: float | None = None
    notes: str | None = None
    resolved_at: datetime | None = None


class OutcomeUpdateSchema(BaseModel):
    """Manual outcome logging payload."""

    outcome: str = Field(
        ...,
        description="win | loss | breakeven | no_trade",
        pattern="^(win|loss|breakeven|no_trade)$",
    )
    realized_return_pct: float | None = Field(
        default=None,
        description="Realized return percentage, e.g. 0.4 for +0.4%",
    )
    notes: str | None = Field(default=None, max_length=500)


class OutcomeStatsSchema(BaseModel):
    """Aggregated outcome stats for logged signals."""

    symbol: str | None = None
    total_logged: int
    resolved: int
    open: int
    wins: int
    losses: int
    breakeven: int
    no_trade: int
    win_rate: float
    avg_return_pct: float
