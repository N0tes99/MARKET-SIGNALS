"""AI Analyst unit tests."""

import pytest
from httpx import AsyncClient

from app.engines.ai_engine import AIAnalyst
from app.engines.evidence_engine.types import EvidenceItem
from app.engines.regime_engine import MarketRegime, RegimeResult
from app.market_data.providers.mock import MockMarketDataProvider
from app.market_data.service import MarketDataService
from app.services.decision_pipeline import DecisionPipelineService, DecisionResult


def _sample_decision() -> DecisionResult:
    md = MarketDataService(provider=MockMarketDataProvider())
    pipeline = DecisionPipelineService(market_data=md)
    return pipeline.evaluate("BTC")


def test_local_explanation_produces_summary() -> None:
    """AI Analyst returns a summary without OpenAI key."""
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
    assert data["source"] in {"local", "openai"}
