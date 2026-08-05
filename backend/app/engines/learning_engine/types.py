"""Learning Engine domain types."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class SignalOutcome(StrEnum):
    """Resolved outcome for a logged signal."""

    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    NO_TRADE = "no_trade"


@dataclass
class SignalRecord:
    """A recorded pipeline decision for learning and similarity."""

    id: UUID
    symbol: str
    timestamp: datetime
    confidence: float
    trade_grade: str
    trade_state: str
    execution_signal: str
    opportunity_score: float
    category_scores: dict[str, float] = field(default_factory=dict)
    expected_value: float | None = None
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    outcome: str | None = None
    realized_return_pct: float | None = None
    notes: str | None = None
    resolved_at: datetime | None = None


@dataclass
class SimilarMatch:
    """A historically similar signal match."""

    id: UUID
    symbol: str
    timestamp: datetime
    confidence: float
    trade_grade: str
    trade_state: str
    similarity: float
    category_scores: dict[str, float] = field(default_factory=dict)
    outcome: str | None = None
    realized_return_pct: float | None = None
