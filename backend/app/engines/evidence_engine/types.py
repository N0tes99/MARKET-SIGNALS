"""Evidence Engine data types."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass
class EvidenceItem:
    """A single piece of evidence from an analysis engine."""

    source: str
    category: str
    score: float
    weight: float
    description: str
    confidence: float = 1.0

    def __post_init__(self) -> None:
        """Validate evidence item fields."""
        if not 0.0 <= self.score <= 100.0:
            msg = f"Evidence score must be 0–100, got {self.score}"
            raise ValueError(msg)


@dataclass
class EvidenceBundle:
    """Aggregated evidence for a single asset at a point in time."""

    symbol: str
    timeframe: str
    items: list[EvidenceItem] = field(default_factory=list)
    total_confidence: float = 0.0
    id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    regime: str | None = None
    regime_confidence: float | None = None
