"""Learning Engine — signal storage and historical similarity."""

from datetime import UTC, datetime
from uuid import uuid4

from app.engines.evidence_engine.types import EvidenceBundle, EvidenceItem
from app.engines.learning_engine.similarity import similarity_from_evidence
from app.engines.learning_engine.store import InMemorySignalStore
from app.engines.learning_engine.types import SignalRecord, SimilarMatch
from app.services.decision_pipeline import DecisionResult


def _category_scores(items: list[EvidenceItem]) -> dict[str, float]:
    return {item.category: item.score for item in items}


class LearningEngine:
    """Stores decisions and finds historically similar evidence patterns."""

    def __init__(self, store: InMemorySignalStore | None = None) -> None:
        self._store = store or InMemorySignalStore()

    @property
    def store(self) -> InMemorySignalStore:
        """Expose the underlying signal store."""
        return self._store

    def record_decision(self, decision: DecisionResult) -> SignalRecord:
        """Persist a pipeline decision into signal history."""
        record = SignalRecord(
            id=uuid4(),
            symbol=decision.symbol,
            timestamp=datetime.now(UTC),
            confidence=decision.evidence.total_confidence,
            trade_grade=decision.opportunity.trade_grade,
            trade_state=decision.trade_state.value,
            execution_signal=decision.execution.signal.value,
            opportunity_score=decision.opportunity.opportunity_score,
            category_scores=_category_scores(decision.evidence.items),
        )
        self._store.add(record)
        return record

    def find_similar(
        self,
        symbol: str,
        evidence: EvidenceBundle,
        limit: int = 5,
        min_similarity: float = 0.85,
    ) -> list[SimilarMatch]:
        """Find past signals with similar evidence fingerprints."""
        normalized = symbol.upper()
        candidates = self._store.list_for_symbol(normalized, limit=100)

        scored: list[SimilarMatch] = []
        for candidate in candidates:
            sim = similarity_from_evidence(evidence, candidate.category_scores)
            if sim < min_similarity:
                continue
            scored.append(
                SimilarMatch(
                    id=candidate.id,
                    symbol=candidate.symbol,
                    timestamp=candidate.timestamp,
                    confidence=candidate.confidence,
                    trade_grade=candidate.trade_grade,
                    trade_state=candidate.trade_state,
                    similarity=round(sim * 100, 1),
                    category_scores=candidate.category_scores,
                )
            )

        scored.sort(key=lambda m: m.similarity, reverse=True)
        return scored[:limit]

    def recent_signals(self, symbol: str, limit: int = 20) -> list[SignalRecord]:
        """Return recent stored signals for an asset."""
        return self._store.list_for_symbol(symbol, limit=limit)
