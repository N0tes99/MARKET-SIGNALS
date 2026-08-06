"""Decision pipeline unit tests."""

from app.market_data.providers.mock import MockMarketDataProvider
from app.market_data.service import MarketDataService
from app.market_data.symbols import TRACKED_SYMBOLS
from app.scoring.grading import TradeState
from app.services.decision_pipeline import DecisionPipelineService


def _pipeline() -> DecisionPipelineService:
    md = MarketDataService(provider=MockMarketDataProvider())
    return DecisionPipelineService(market_data=md)


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
