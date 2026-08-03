"""Evidence contributor protocol."""

from typing import Protocol

from app.engines.evidence_engine.types import EvidenceItem


class EvidenceContributor(Protocol):
    """Protocol for engines that supply evidence to the Evidence Engine."""

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return evidence items for the given asset."""
        ...
