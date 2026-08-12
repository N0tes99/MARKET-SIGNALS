"""AI Analyst unit tests."""

import pytest
from httpx import AsyncClient

from app.engines.ai_engine import AIAnalyst
from app.engines.evidence_engine.types import EvidenceItem
from app.market_data.providers.mock import MockMarketDataProvider
from app.market_data.service import MarketDataService
from app.services.decision_pipeline import DecisionPipelineService, DecisionResult


def _sample_decision() -> DecisionResult:
    md = MarketDataService(provider=MockMarketDataProvider())
    pipeline = DecisionPipelineService(market_data=md)
    return pipeline.evaluate("BTC")


def test_local_explanation_produces_summary(monkeypatch) -> None:
    """AI Analyst returns a summary without OpenAI key."""
    from app.engines.ai_engine import engine as ai_mod

    monkeypatch.setattr(ai_mod.settings, "openai_api_key", "")
    monkeypatch.setattr(ai_mod.settings, "gemini_api_key", "")
    analyst = AIAnalyst()
    decision = _sample_decision()
    explanation = analyst.explain_decision(decision)

    assert explanation.symbol == "BTC"
    assert explanation.summary
    assert explanation.confidence > 0
    assert explanation.source == "local"


def test_conflict_detection() -> None:
    """Conflicting trend and macro scores are flagged."""
    analyst = AIAnalyst()
    items = [
        EvidenceItem("t", "Trend", 75.0, 20.0, "bullish"),
        EvidenceItem("m", "Macro", 30.0, 10.0, "weak macro"),
        EvidenceItem("mo", "Momentum", 50.0, 15.0, "neutral"),
    ]
    conflicts = analyst._detect_conflicts(items)
    assert any("macro" in c.lower() for c in conflicts)


@pytest.mark.asyncio
async def test_analysis_api_endpoint(client: AsyncClient) -> None:
    """Analysis endpoint returns AI explanation schema."""
    response = await client.get("/api/v1/assets/BTC/analysis")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "BTC"
    assert "summary" in data
    assert data["source"] in {"local", "openai", "gemini"}


def test_local_summary_uses_fear_greed_and_reddit(monkeypatch) -> None:
    from app.engines.evidence_engine.types import EvidenceBundle
    from app.engines.execution_engine.engine import ExecutionResult, ExecutionSignal
    from app.engines.opportunity_engine.engine import OpportunityResult
    from app.scoring.grading import TradeState

    items = [
        EvidenceItem(
            "sentiment_engine",
            "Sentiment",
            34.0,
            2.0,
            "Fear & Greed 82 (Extreme Greed) — extreme greed, caution",
        ),
        EvidenceItem(
            "reddit_social",
            "Sentiment",
            38.0,
            1.0,
            "Reddit: crowded bullish chatter — caution (12 posts, eng 400, lean +0.80)",
        ),
        EvidenceItem("t", "Trend", 72.0, 20.0, "uptrend intact"),
        EvidenceItem("mo", "Momentum", 68.0, 15.0, "thrust higher"),
        EvidenceItem("ev", "Events", 55.0, 5.0, "no near catalyst"),
    ]
    evidence = EvidenceBundle(
        symbol="NVDA",
        timeframe="1h",
        items=items,
        total_confidence=62.0,
    )
    decision = DecisionResult(
        symbol="NVDA",
        evidence=evidence,
        opportunity=OpportunityResult(
            symbol="NVDA",
            opportunity_score=62.0,
            trade_grade="C",
            expected_value=0.0,
            trade_state=TradeState.WATCH,
            description="NVDA: Building evidence",
        ),
        execution=ExecutionResult(
            symbol="NVDA",
            signal=ExecutionSignal.WATCH,
            confidence=62.0,
            description="watch",
        ),
        risk=None,
        trade_state=TradeState.WATCH,
        summary="NVDA — watch",
    )
    from app.engines.ai_engine import engine as ai_mod

    monkeypatch.setattr(ai_mod.settings, "openai_api_key", "")
    monkeypatch.setattr(ai_mod.settings, "gemini_api_key", "")
    explanation = AIAnalyst().explain_decision(decision)
    assert explanation.source == "local"
    assert "Crowd:" in explanation.summary
    assert "Fear & Greed" in explanation.summary
    assert "Reddit" in explanation.summary
    assert any("crowded" in c.lower() or "chase" in c.lower() for c in explanation.conflicts)
