"""Phase A signal engine tests — correlation, volatility, events."""

from app.engines.correlation_engine import CorrelationEngine
from app.engines.event_engine import EventEngine
from app.engines.volatility_engine import VolatilityEngine, score_from_vix
from app.market_data.providers.mock import MockMarketDataProvider
from app.market_data.service import MarketDataService
from app.scoring.weights import ScoringCategory


def _md() -> MarketDataService:
    return MarketDataService(provider=MockMarketDataProvider())


def test_correlation_engine_contributes_evidence() -> None:
    engine = CorrelationEngine(_md())
    items = engine.contribute_evidence("BTC")
    assert len(items) == 1
    assert items[0].category == ScoringCategory.CORRELATION.value
    assert 0 <= items[0].score <= 100


def test_volatility_engine_contributes_evidence() -> None:
    engine = VolatilityEngine(_md())
    items = engine.contribute_evidence("BTC")
    assert items[0].category == ScoringCategory.VOLATILITY.value
    assert 0 <= items[0].score <= 100


def test_score_from_vix_levels() -> None:
    low, _ = score_from_vix(12.0)
    high, _ = score_from_vix(35.0)
    assert low > high


def test_event_engine_contributes_evidence() -> None:
    engine = EventEngine(fred_api_key=None)
    items = engine.contribute_evidence("AAPL")
    assert items[0].category == ScoringCategory.EVENTS.value
    assert 0 <= items[0].score <= 100


def test_event_engine_crypto_fallback() -> None:
    engine = EventEngine(fred_api_key=None)
    items = engine.contribute_evidence("BTC")
    assert "Events:" in items[0].description
