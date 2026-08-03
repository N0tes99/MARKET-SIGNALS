"""Analysis engine unit tests."""

from app.engines.buyer_seller_engine import BuyerSellerEngine
from app.engines.evidence_engine import EvidenceEngine
from app.engines.regime_engine import RegimeEngine
from app.engines.risk_engine import RiskEngine
from app.engines.trend_engine import TrendEngine
from app.market_data.providers.mock import MockMarketDataProvider
from app.market_data.service import MarketDataService


def _mock_service() -> MarketDataService:
    """Build a market data service with synthetic trending data."""
    return MarketDataService(provider=MockMarketDataProvider())


def test_trend_engine_uptrend_detection() -> None:
    """Trend engine detects bullish bias on synthetic uptrend data."""
    engine = TrendEngine(_mock_service())
    result = engine.analyze("BTC")
    assert result is not None
    assert result.confidence > 0
    assert result.structure_score >= 50


def test_buyer_seller_engine_produces_scores() -> None:
    """Buyer/seller engine returns non-zero flow metrics."""
    engine = BuyerSellerEngine(_mock_service())
    result = engine.analyze("BTC")
    assert result is not None
    assert 0 <= result.buyer_strength <= 100
    assert 0 <= result.momentum <= 100


def test_risk_engine_calculates_stop_and_target() -> None:
    """Risk engine computes stop loss below current price."""
    engine = RiskEngine(_mock_service())
    result = engine.assess("BTC")
    assert result is not None
    assert result.stop_loss < result.take_profit
    assert result.risk_reward_ratio > 0


def test_regime_engine_classifies_trending() -> None:
    """Regime engine classifies synthetic uptrend as trending."""
    engine = RegimeEngine(_mock_service())
    result = engine.classify("BTC")
    assert result.regime in {"Trending", "Ranging", "Volatile", "Quiet"}


def test_evidence_engine_nonzero_confidence_with_mock_data() -> None:
    """Full evidence pipeline produces non-zero confidence on mock data."""
    md = _mock_service()
    engine = EvidenceEngine(market_data=md)
    bundle = engine.accumulate("BTC")
    assert bundle.total_confidence > 0
    assert len(bundle.items) == 10
