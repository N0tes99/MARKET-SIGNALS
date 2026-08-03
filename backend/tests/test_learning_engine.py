"""Learning engine and backtesting tests."""

from datetime import UTC, datetime
from uuid import uuid4

from app.engines.evidence_engine.types import EvidenceBundle, EvidenceItem
from app.engines.learning_engine import LearningEngine
from app.engines.learning_engine.similarity import cosine_similarity, evidence_to_vector
from app.engines.learning_engine.store import InMemorySignalStore
from app.engines.learning_engine.types import SignalRecord
from app.engines.execution_engine import ExecutionResult, ExecutionSignal
from app.engines.opportunity_engine import OpportunityResult
from app.scoring.grading import TradeState
from app.services.decision_pipeline import DecisionResult


def _sample_decision(symbol: str = "BTC", confidence: float = 62.0) -> DecisionResult:
    items = [
        EvidenceItem("t", "Trend", 65.0, 20.0, "bullish"),
        EvidenceItem("m", "Momentum", 58.0, 15.0, "neutral"),
        EvidenceItem("v", "Volume", 50.0, 10.0, "avg"),
        EvidenceItem("s", "Structure", 55.0, 20.0, "ok"),
        EvidenceItem("r", "Risk", 60.0, 15.0, "moderate"),
        EvidenceItem("mac", "Macro", 52.0, 10.0, "neutral"),
        EvidenceItem("d", "Derivatives", 48.0, 10.0, "flat"),
    ]
    evidence = EvidenceBundle(
        symbol=symbol,
        timeframe="1h",
        items=items,
        total_confidence=confidence,
    )
    opportunity = OpportunityResult(
        symbol=symbol,
        opportunity_score=confidence,
        trade_grade="C",
        expected_value=0.5,
        trade_state=TradeState.WATCH,
        description="test",
    )
    execution = ExecutionResult(
        symbol=symbol,
        signal=ExecutionSignal.WATCH,
        confidence=confidence,
        description="watch",
    )
    return DecisionResult(
        symbol=symbol,
        evidence=evidence,
        opportunity=opportunity,
        execution=execution,
        risk=None,
        trade_state=TradeState.WATCH,
        summary="test summary",
    )


def test_cosine_similarity_identical_vectors() -> None:
    vec = [50.0, 60.0, 70.0]
    assert cosine_similarity(vec, vec) == 1.0


def test_learning_engine_records_and_finds_similar() -> None:
    engine = LearningEngine(store=InMemorySignalStore())
    decision = _sample_decision()

    engine.record_decision(decision)
    engine.record_decision(decision)

    matches = engine.find_similar("BTC", decision.evidence, limit=5, min_similarity=0.9)
    assert len(matches) >= 1
    assert matches[0].similarity >= 90.0


def test_evidence_to_vector_fixed_order() -> None:
    items = [EvidenceItem("t", "Trend", 80.0, 20.0, "x")]
    vec = evidence_to_vector(items)
    assert vec[0] == 80.0
    assert vec[1] == 50.0  # default for missing categories
