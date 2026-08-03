"""Learning Engine domain types."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


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
