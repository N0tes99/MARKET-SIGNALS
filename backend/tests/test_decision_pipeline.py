"""Decision pipeline unit tests."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.engines.evidence_engine.types import EvidenceBundle, EvidenceItem
from app.engines.execution_engine import ExecutionResult, ExecutionSignal
from app.engines.learning_engine import LearningEngine, SignalOutcome
from app.engines.learning_engine.store import InMemorySignalStore
from app.engines.learning_engine.types import SignalRecord
from app.engines.opportunity_engine import OpportunityEngine, OpportunityResult
from app.engines.risk_engine import RiskAssessment
from app.market_data.providers.mock import MockMarketDataProvider
from app.market_data.service import MarketDataService
from app.market_data.symbols import TRACKED_SYMBOLS
from app.scoring.grading import TradeState, blend_expected_value, compute_expected_value
from app.services.decision_pipeline import _EVAL_CACHE, DecisionPipelineService


def _pipeline(learning: LearningEngine | None = None) -> DecisionPipelineService:
    md = MarketDataService(provider=MockMarketDataProvider())
    return DecisionPipelineService(market_data=md, learning_engine=learning)


def _risk(
    *,
    score: float = 60.0,
    risk_reward_ratio: float = 1.8,
) -> RiskAssessment:
    return RiskAssessment(
        symbol="BTC",
        position_size=1.0,
        stop_loss=90.0,
        take_profit=110.0,
        max_drawdown=1.0,
        risk_percent=1.0,
        risk_reward_ratio=risk_reward_ratio,
        score=score,
        description="test risk",
    )


def _opportunity(
    score: float = 75.0,
    state: TradeState = TradeState.WATCH,
) -> OpportunityResult:
    return OpportunityResult(
        symbol="BTC",
        opportunity_score=score,
        trade_grade="B",
        expected_value=0.5,
        trade_state=state,
        description="test opp",
    )


def _execution(signal: ExecutionSignal = ExecutionSignal.EXECUTE) -> ExecutionResult:
    return ExecutionResult(
        symbol="BTC",
        signal=signal,
        confidence=80.0,
        description="test exec",
    )


def _evidence(confidence: float = 75.0) -> EvidenceBundle:
    return EvidenceBundle(
        symbol="BTC",
        timeframe="1h",
        items=[
            EvidenceItem("t", "Trend", 70.0, 20.0, "bullish"),
            EvidenceItem("m", "Momentum", 60.0, 15.0, "ok"),
            EvidenceItem("v", "Volume", 55.0, 10.0, "ok"),
            EvidenceItem("s", "Structure", 65.0, 20.0, "ok"),
            EvidenceItem("r", "Risk", 50.0, 15.0, "ok"),
            EvidenceItem("mac", "Macro", 50.0, 10.0, "ok"),
            EvidenceItem("d", "Derivatives", 50.0, 10.0, "ok"),
        ],
        total_confidence=confidence,
    )


def test_pipeline_evaluate_untracked_us_ticker() -> None:
    """Tape names like CRDO must not crash confirm via get_asset_class."""
    pipeline = _pipeline()
    decision = pipeline.evaluate("CRDO")
    assert decision.symbol == "CRDO"
    assert decision.evidence.total_confidence >= 0
    assert decision.opportunity.trade_grade


def test_pipeline_produces_decision() -> None:
    """Pipeline returns a complete decision for mock data."""
    pipeline = _pipeline()
    decision = pipeline.evaluate("BTC")

    assert decision.symbol == "BTC"
    assert decision.evidence.total_confidence > 0
    assert decision.opportunity.trade_grade != "F"
    assert decision.execution.signal in {"WAIT", "WATCH", "EXECUTE"}
    assert decision.trade_state in TradeState


def test_pipeline_ranks_by_score() -> None:
    """Ranked results are sorted by opportunity score descending."""
    pipeline = _pipeline()
    ranked = pipeline.rank_all(list(TRACKED_SYMBOLS))
    scores = [d.opportunity.opportunity_score for d in ranked]
    assert scores == sorted(scores, reverse=True)


def test_opportunity_grade_mapping() -> None:
    """High confidence mock data should not receive F grade."""
    pipeline = _pipeline()
    decision = pipeline.evaluate("BTC")
    assert decision.opportunity.trade_grade in {"A+", "A", "B", "C", "D"}


def test_risk_veto_downgrades_execute_to_watch() -> None:
    """Weak risk quality/R:R vetoes EXECUTE down to WATCH."""
    pipeline = _pipeline()
    state = pipeline._resolve_trade_state(
        "BTC",
        _opportunity(75.0),
        _execution(ExecutionSignal.EXECUTE),
        _risk(score=30.0, risk_reward_ratio=1.0),
        _evidence(75.0),
    )
    assert state == TradeState.WATCH


def test_risk_clears_allows_execute() -> None:
    """Approved risk with EXECUTE timing yields EXECUTE."""
    pipeline = _pipeline()
    state = pipeline._resolve_trade_state(
        "BTC",
        _opportunity(75.0),
        _execution(ExecutionSignal.EXECUTE),
        _risk(score=60.0, risk_reward_ratio=1.8),
        _evidence(75.0),
    )
    assert state == TradeState.EXECUTE


def test_manage_when_open_active_signal() -> None:
    """Open EXECUTE learning signal + holdable conditions → MANAGE."""
    learning = LearningEngine(store=InMemorySignalStore())
    learning.store.add(
        SignalRecord(
            id=uuid4(),
            symbol="BTC",
            timestamp=datetime.now(UTC),
            confidence=80.0,
            trade_grade="A",
            trade_state=TradeState.EXECUTE.value,
            execution_signal=ExecutionSignal.EXECUTE.value,
            opportunity_score=80.0,
            outcome=None,
        )
    )
    pipeline = _pipeline(learning)
    state = pipeline._resolve_trade_state(
        "BTC",
        _opportunity(72.0),
        _execution(ExecutionSignal.WATCH),
        _risk(score=55.0, risk_reward_ratio=1.5),
        _evidence(72.0),
    )
    assert state == TradeState.MANAGE


def test_exit_when_open_active_degrades() -> None:
    """Open manage context + WAIT / collapsed evidence → EXIT."""
    learning = LearningEngine(store=InMemorySignalStore())
    learning.store.add(
        SignalRecord(
            id=uuid4(),
            symbol="BTC",
            timestamp=datetime.now(UTC),
            confidence=80.0,
            trade_grade="A",
            trade_state=TradeState.MANAGE.value,
            execution_signal=ExecutionSignal.EXECUTE.value,
            opportunity_score=80.0,
            outcome=None,
        )
    )
    pipeline = _pipeline(learning)
    state = pipeline._resolve_trade_state(
        "BTC",
        _opportunity(40.0),
        _execution(ExecutionSignal.WAIT),
        _risk(score=20.0, risk_reward_ratio=1.0),
        _evidence(40.0),
    )
    assert state == TradeState.EXIT


def test_exit_when_learning_outcome_closed() -> None:
    """Recently closed outcome with degraded base → EXIT."""
    learning = LearningEngine(store=InMemorySignalStore())
    learning.store.add(
        SignalRecord(
            id=uuid4(),
            symbol="BTC",
            timestamp=datetime.now(UTC),
            confidence=70.0,
            trade_grade="B",
            trade_state=TradeState.EXECUTE.value,
            execution_signal=ExecutionSignal.EXECUTE.value,
            opportunity_score=70.0,
            outcome=SignalOutcome.WIN.value,
            realized_return_pct=1.2,
            resolved_at=datetime.now(UTC),
        )
    )
    pipeline = _pipeline(learning)
    state = pipeline._resolve_trade_state(
        "BTC",
        _opportunity(40.0),
        _execution(ExecutionSignal.WAIT),
        _risk(score=20.0, risk_reward_ratio=1.0),
        _evidence(40.0),
    )
    assert state == TradeState.EXIT


def test_learning_ev_blend_with_enough_samples() -> None:
    """n>=3 resolved trades blend historical EV into opportunity EV."""
    learning = LearningEngine(store=InMemorySignalStore())
    for ret in (2.0, 1.5, -0.5):
        outcome = SignalOutcome.WIN if ret > 0 else SignalOutcome.LOSS
        learning.store.add(
            SignalRecord(
                id=uuid4(),
                symbol="BTC",
                timestamp=datetime.now(UTC),
                confidence=70.0,
                trade_grade="B",
                trade_state=TradeState.EXECUTE.value,
                execution_signal=ExecutionSignal.EXECUTE.value,
                opportunity_score=70.0,
                outcome=outcome.value,
                realized_return_pct=ret,
                resolved_at=datetime.now(UTC),
            )
        )

    formula = compute_expected_value(70.0, 1.5)
    blended = learning.blend_expected_value("BTC", formula, 1.5)
    assert blended != formula
    assert blended == blend_expected_value(
        formula,
        1.5,
        hit_rate_pct=round((2 / 3) * 100, 1),
        avg_return_pct=round((2.0 + 1.5 - 0.5) / 3, 3),
        sample_count=3,
    )


def test_learning_ev_fallback_without_samples() -> None:
    """Empty learning store keeps formula EV unchanged."""
    learning = LearningEngine(store=InMemorySignalStore())
    formula = compute_expected_value(70.0, 1.5)
    assert learning.blend_expected_value("ETH", formula, 1.5) == formula


def test_pipeline_applies_learning_ev(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pipeline evaluate path applies blended EV when learning has history."""
    _EVAL_CACHE.clear()
    learning = LearningEngine(store=InMemorySignalStore())
    for ret in (3.0, 2.0, 1.0):
        learning.store.add(
            SignalRecord(
                id=uuid4(),
                symbol="BTC",
                timestamp=datetime.now(UTC),
                confidence=80.0,
                trade_grade="A",
                trade_state=TradeState.EXECUTE.value,
                execution_signal=ExecutionSignal.EXECUTE.value,
                opportunity_score=80.0,
                outcome=SignalOutcome.WIN.value,
                realized_return_pct=ret,
                resolved_at=datetime.now(UTC),
            )
        )

    pipeline = _pipeline(learning)
    original = OpportunityEngine.evaluate

    def _wrap(self, symbol, evidence, risk_reward_ratio=1.5):  # noqa: ANN001
        result = original(self, symbol, evidence, risk_reward_ratio)
        return replace(result, expected_value=0.25)

    monkeypatch.setattr(OpportunityEngine, "evaluate", _wrap)
    decision = pipeline.evaluate("BTC")
    assert decision.opportunity.expected_value != 0.25


@pytest.mark.asyncio
async def test_decision_route(client: AsyncClient) -> None:
    """GET /api/v1/assets/{symbol}/decision returns pipeline fields."""
    response = await client.get("/api/v1/assets/BTC/decision")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "BTC"
    assert data["trade_state"] in {s.value for s in TradeState}
    assert "opportunity_score" in data
    assert "execution" in data
    assert "expected_value" in data
