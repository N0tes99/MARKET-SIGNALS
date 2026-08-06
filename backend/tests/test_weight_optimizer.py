"""Weight optimizer tests."""

from app.market_data.providers.mock import MockMarketDataProvider
from app.market_data.service import MarketDataService
from app.scoring.optimizer import WeightOptimizer, confidence_from_scores
from app.scoring.presets import WEIGHT_PRESETS
from app.scoring.weight_config import WeightConfig
from app.scoring.weights import ScoringCategory


def test_optimize_returns_ranked_presets() -> None:
    md = MarketDataService(provider=MockMarketDataProvider())
    optimizer = WeightOptimizer(market_data=md, weight_config=WeightConfig())
    result = optimizer.optimize("BTC")

    assert result.symbol == "BTC"
    assert len(result.results) == len(WEIGHT_PRESETS)
    assert result.recommended_preset in WEIGHT_PRESETS
    assert abs(sum(result.recommended_weights.values()) - 100.0) < 0.1


def test_apply_preset_updates_active_weights() -> None:
    config = WeightConfig()
    optimizer = WeightOptimizer(
        market_data=MarketDataService(provider=MockMarketDataProvider()),
        weight_config=config,
    )

    assert config.is_regime_auto() is True
    optimizer.apply_preset("momentum_focused")
    preset, weights = optimizer.active_weights()

    assert preset == "momentum_focused"
    assert weights[ScoringCategory.MOMENTUM] > weights[ScoringCategory.TREND]
    assert config.is_regime_auto() is False

    optimizer.reset()
    assert config.is_regime_auto() is True
    assert config.get_preset_name() == "default"


def test_confidence_from_scores_uses_weights() -> None:
    scores = dict.fromkeys(ScoringCategory, 80.0)
    scores[ScoringCategory.MACRO] = 20.0

    heavy_trend = confidence_from_scores(scores, WEIGHT_PRESETS["trend_focused"])
    heavy_macro = confidence_from_scores(scores, WEIGHT_PRESETS["macro_aware"])

    assert heavy_trend > heavy_macro
