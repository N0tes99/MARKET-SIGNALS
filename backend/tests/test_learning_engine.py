"""Learning engine and outcome logging tests."""

from uuid import uuid4

import pytest

from app.engines.evidence_engine.types import EvidenceBundle, EvidenceItem
from app.engines.execution_engine import ExecutionResult, ExecutionSignal
from app.engines.learning_engine import LearningEngine, SignalOutcome
from app.engines.learning_engine.similarity import cosine_similarity, evidence_to_vector
from app.engines.learning_engine.store import InMemorySignalStore
from app.engines.opportunity_engine import OpportunityResult
from app.engines.risk_engine import RiskAssessment
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
    risk = RiskAssessment(
        symbol=symbol,
        position_size=1.0,
        stop_loss=100.0,
        take_profit=103.0,
        max_drawdown=1.0,
        risk_percent=1.0,
        risk_reward_ratio=1.5,
        score=60.0,
        description="test risk",
    )
    return DecisionResult(
        symbol=symbol,
        evidence=evidence,
        opportunity=opportunity,
        execution=execution,
        risk=risk,
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


def test_record_decision_captures_risk_levels() -> None:
    engine = LearningEngine(store=InMemorySignalStore())
    record = engine.record_decision(_sample_decision("SPY", confidence=68.0))
    assert record.confidence == 68.0
    assert record.stop_loss == 100.0
    assert record.take_profit == 103.0
    assert record.entry_price is not None
    assert record.outcome is None


def test_record_outcome_win() -> None:
    engine = LearningEngine(store=InMemorySignalStore())
    record = engine.record_decision(_sample_decision("SPY", confidence=68.0))
    updated = engine.record_outcome(
        record.id,
        SignalOutcome.WIN,
        realized_return_pct=0.4,
        notes="SPY +3pts",
    )
    assert updated.outcome == "win"
    assert updated.realized_return_pct == 0.4
    assert updated.notes == "SPY +3pts"
    assert updated.resolved_at is not None

    stats = engine.outcome_stats("SPY")
    assert stats["wins"] == 1
    assert stats["win_rate"] == 100.0
    assert stats["avg_return_pct"] == 0.4


def test_record_outcome_missing_raises() -> None:
    engine = LearningEngine(store=InMemorySignalStore())
    with pytest.raises(KeyError):
        engine.record_outcome(uuid4(), SignalOutcome.LOSS)
