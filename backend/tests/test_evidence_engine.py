"""Evidence Engine tests."""

import pytest

from app.engines.evidence_engine import EvidenceEngine
from app.engines.evidence_engine.types import EvidenceItem
from app.engines.regime_engine import MarketRegime, RegimeResult
from app.market_data.providers.mock import MockMarketDataProvider
from app.market_data.service import MarketDataService
from app.scoring.calculator import calculate_total_confidence
from app.scoring.weight_config import get_weight_config
from app.scoring.weights import (
    DEFAULT_WEIGHTS,
    REGIME_WEIGHT_PROFILES,
    ScoringCategory,
    WeightProfile,
)


@pytest.fixture(autouse=True)
def _restore_weight_config() -> None:
    """Keep the process-local WeightConfig singleton clean across tests."""
    get_weight_config().reset()
    yield
    get_weight_config().reset()


class _NeutralRegimeEngine:
    """Regime stub; scoring uses WeightConfig when regime_auto is off."""

    def classify(self, symbol: str, timeframe: str = "1h") -> RegimeResult:
        del symbol, timeframe
        return RegimeResult(
            regime=MarketRegime.RANGING,
            confidence=0.0,
            weight_profile=WeightProfile.CHOPPY,
            description="neutral test regime",
        )


def _mock_engine(collectors=None) -> EvidenceEngine:
    """Build evidence engine with mock market data and fixed WeightConfig weights."""
    get_weight_config().apply(dict(DEFAULT_WEIGHTS), preset_name="test_fixed")
    md = MarketDataService(provider=MockMarketDataProvider())
    return EvidenceEngine(
        collectors=collectors,
        regime_engine=_NeutralRegimeEngine(),
        market_data=md,
    )


def test_accumulate_returns_all_categories() -> None:
    """Evidence accumulation includes all scoring categories."""
    engine = _mock_engine()
    bundle = engine.accumulate("BTC")

    assert bundle.symbol == "BTC"
    assert bundle.timeframe == "1h"
    categories = {item.category for item in bundle.items}
    assert categories == {category.value for category in DEFAULT_WEIGHTS}
    assert bundle.regime == "Ranging"
    assert bundle.regime_confidence == 0.0


def test_accumulate_nonzero_confidence_with_mock_data() -> None:
    """Mock market data produces non-zero total confidence."""
    engine = _mock_engine()
    bundle = engine.accumulate("ETH")
    assert bundle.total_confidence > 0


def test_accumulate_normalizes_symbol() -> None:
    """Symbol is normalized to uppercase."""
    engine = _mock_engine()
    bundle = engine.accumulate("btc")
    assert bundle.symbol == "BTC"


def test_custom_collector_injection() -> None:
    """Custom collectors can be injected for testing."""
    trend_weight = get_weight_config().get_weights()[ScoringCategory.TREND]
    custom_item = EvidenceItem(
        source="test_engine",
        category="Trend",
        score=100.0,
        weight=trend_weight,
        description="Test trend signal",
    )

    class CustomCollector:
        def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
            del symbol, timeframe
            return [custom_item]

    engine = _mock_engine(collectors=[CustomCollector()])
    bundle = engine.accumulate("SOL")

    assert len(bundle.items) == 1
    expected = calculate_total_confidence(
        [custom_item],
        weights=get_weight_config().get_weights(),
    )
    assert bundle.total_confidence == expected


def test_regime_auto_uses_profile_weights() -> None:
    """With regime_auto on, scoring uses the regime profile table."""
    assert get_weight_config().is_regime_auto() is True

    trend_w = REGIME_WEIGHT_PROFILES[WeightProfile.CHOPPY][ScoringCategory.TREND]
    item = EvidenceItem("t", "Trend", 100.0, trend_w, "t")

    class OneCollector:
        def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
            del symbol, timeframe
            return [item]

    md = MarketDataService(provider=MockMarketDataProvider())
    engine = EvidenceEngine(
        collectors=[OneCollector()],
        regime_engine=_NeutralRegimeEngine(),
        market_data=md,
    )
    bundle = engine.accumulate("BTC")
    expected = calculate_total_confidence(
        [item],
        weights=REGIME_WEIGHT_PROFILES[WeightProfile.CHOPPY],
    )
    assert bundle.total_confidence == expected
