"""Learning Engine — signal storage, outcomes, and historical similarity."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.engines.evidence_engine.types import EvidenceBundle, EvidenceItem
from app.engines.learning_engine.similarity import similarity_from_evidence
from app.engines.learning_engine.store import InMemorySignalStore, SignalStore
from app.engines.learning_engine.types import SignalOutcome, SignalRecord, SimilarMatch
from app.services.decision_pipeline import DecisionResult


def _category_scores(items: list[EvidenceItem]) -> dict[str, float]:
    return {item.category: item.score for item in items}


class LearningEngine:
    """Stores decisions and finds historically similar evidence patterns."""

    def __init__(self, store: SignalStore | None = None) -> None:
        self._store = store or InMemorySignalStore()

    @property
    def store(self) -> SignalStore:
        """Expose the underlying signal store."""
        return self._store

    def record_decision(self, decision: DecisionResult) -> SignalRecord:
        """Persist a pipeline decision into signal history."""
        risk = decision.risk
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
            expected_value=decision.opportunity.expected_value,
            entry_price=None,
            stop_loss=risk.stop_loss if risk else None,
            take_profit=risk.take_profit if risk else None,
        )
        # Derive approximate entry from stop/target midpoint when R:R known
        if risk and risk.stop_loss and risk.take_profit and risk.risk_reward_ratio > 0:
            # entry ≈ stop + (take - stop) / (1 + R:R) for long setups
            span = risk.take_profit - risk.stop_loss
            if span > 0:
                risk_portion = span / (1.0 + risk.risk_reward_ratio)
                record.entry_price = round(risk.stop_loss + risk_portion, 6)

        self._store.add(record)
        return record

    def record_outcome(
        self,
        record_id: UUID,
        outcome: SignalOutcome | str,
        realized_return_pct: float | None = None,
        notes: str | None = None,
    ) -> SignalRecord:
        """Attach a realized outcome to an existing signal record."""
        record = self._store.get(record_id)
        if record is None:
            msg = f"Signal record '{record_id}' not found"
            raise KeyError(msg)

        normalized = SignalOutcome(outcome) if not isinstance(outcome, SignalOutcome) else outcome
        record.outcome = normalized.value
        record.realized_return_pct = realized_return_pct
        if notes is not None:
            record.notes = notes
        record.resolved_at = datetime.now(UTC)

        updated = self._store.update(record)
        if updated is None:
            msg = f"Failed to update signal record '{record_id}'"
            raise RuntimeError(msg)
        return updated

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
                    outcome=candidate.outcome,
                    realized_return_pct=candidate.realized_return_pct,
                )
            )

        scored.sort(key=lambda m: m.similarity, reverse=True)
        return scored[:limit]

    def recent_signals(self, symbol: str, limit: int = 20) -> list[SignalRecord]:
        """Return recent stored signals for an asset."""
        return self._store.list_for_symbol(symbol, limit=limit)

    def outcome_stats(self, symbol: str | None = None) -> dict[str, float | int]:
        """Summarize resolved outcomes for a symbol or all symbols."""
        records = (
            self._store.list_for_symbol(symbol, limit=500)
            if symbol
            else self._store.list_all(limit=1000)
        )
        resolved = [r for r in records if r.outcome]
        wins = sum(1 for r in resolved if r.outcome == SignalOutcome.WIN.value)
        losses = sum(1 for r in resolved if r.outcome == SignalOutcome.LOSS.value)
        breakeven = sum(1 for r in resolved if r.outcome == SignalOutcome.BREAKEVEN.value)
        no_trade = sum(1 for r in resolved if r.outcome == SignalOutcome.NO_TRADE.value)
        traded = wins + losses + breakeven
        returns = [r.realized_return_pct for r in resolved if r.realized_return_pct is not None]
        return {
            "total_logged": len(records),
            "resolved": len(resolved),
            "open": len(records) - len(resolved),
            "wins": wins,
            "losses": losses,
            "breakeven": breakeven,
            "no_trade": no_trade,
            "win_rate": round((wins / traded) * 100, 1) if traded else 0.0,
            "avg_return_pct": round(sum(returns) / len(returns), 3) if returns else 0.0,
        }
