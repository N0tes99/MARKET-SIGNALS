"""Phase B signal engine tests — sector RS, deeper derivatives, on-chain, sentiment."""

from app.engines.onchain_engine import OnChainEngine, score_btc_mempool, score_vol_mcap
from app.engines.sector_rs_engine import SectorRSEngine, score_relative_strength
from app.engines.sentiment_engine import SentimentEngine, score_from_fear_greed
from app.market_data.providers.bybit_derivatives import (
    funding_trend,
    score_derivatives_composite,
)
from app.market_data.providers.mock import MockMarketDataProvider
from app.market_data.service import MarketDataService
from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory, validate_weights


def _md() -> MarketDataService:
    return MarketDataService(provider=MockMarketDataProvider())


def test_phase_b_weights_sum_to_100() -> None:
    validate_weights(DEFAULT_WEIGHTS)
    assert ScoringCategory.SECTOR_RS in DEFAULT_WEIGHTS
    assert ScoringCategory.ON_CHAIN in DEFAULT_WEIGHTS
    assert ScoringCategory.SENTIMENT in DEFAULT_WEIGHTS


def test_score_relative_strength_buckets() -> None:
    leader, _ = score_relative_strength(5.0)
    lagger, _ = score_relative_strength(-5.0)
    assert leader > lagger


def test_sector_rs_engine_contributes_evidence() -> None:
    engine = SectorRSEngine(_md())
    items = engine.contribute_evidence("AAPL")
    assert len(items) == 1
    assert items[0].category == ScoringCategory.SECTOR_RS.value
    assert 0 <= items[0].score <= 100


def test_sector_rs_crypto_benchmark() -> None:
    engine = SectorRSEngine(_md())
    items = engine.contribute_evidence("ETH")
    assert items[0].category == ScoringCategory.SECTOR_RS.value
    assert 0 <= items[0].score <= 100


def test_score_derivatives_composite_crowding() -> None:
    neutral, _ = score_derivatives_composite(0.0001, [0.0001] * 6, 0.0)
    crowded, desc = score_derivatives_composite(
        0.001,
        [0.0002, 0.0003, 0.0004, 0.0008, 0.0009, 0.001],
        8.0,
    )
    assert crowded < neutral
    assert "crowded" in desc or "Funding" in desc


def test_funding_trend_direction() -> None:
    rising = funding_trend([0.0001, 0.0001, 0.0001, 0.001, 0.001, 0.001])
    falling = funding_trend([0.001, 0.001, 0.001, 0.0001, 0.0001, 0.0001])
    assert rising is not None and falling is not None
    assert rising > 0
    assert falling < 0


def test_derivatives_engine_mock_snapshot(monkeypatch) -> None:
    from app.engines.derivatives_engine import DerivativesEngine

    monkeypatch.setattr(
        "app.engines.derivatives_engine.engine.fetch_derivatives_depth",
        lambda symbol: None,
    )
    engine = DerivativesEngine(_md())
    items = engine.contribute_evidence("BTC")
    assert items[0].category == ScoringCategory.DERIVATIVES.value
    assert 0 <= items[0].score <= 100


def test_derivatives_engine_equity_neutral() -> None:
    from app.engines.derivatives_engine import DerivativesEngine

    engine = DerivativesEngine(_md())
    items = engine.contribute_evidence("AAPL")
    assert items[0].score == 50.0
    assert "N/A" in items[0].description


def test_score_btc_mempool_and_vol_mcap() -> None:
    calm, _ = score_btc_mempool(3.0)
    hot, _ = score_btc_mempool(80.0)
    assert calm > hot
    quiet, _ = score_vol_mcap(0.01)
    speculative, _ = score_vol_mcap(0.35)
    assert quiet > speculative


def test_onchain_equity_neutral() -> None:
    engine = OnChainEngine()
    items = engine.contribute_evidence("SPY")
    assert items[0].category == ScoringCategory.ON_CHAIN.value
    assert items[0].score == 50.0


def test_score_from_fear_greed() -> None:
    fear, _ = score_from_fear_greed(15, "Extreme Fear")
    greed, _ = score_from_fear_greed(85, "Extreme Greed")
    assert fear > greed


def test_sentiment_engine_contributes_evidence(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.sentiment_engine.engine.fetch_fear_greed",
        lambda: (45, "Fear"),
    )
    engine = SentimentEngine()
    items = engine.contribute_evidence("BTC")
    assert items[0].category == ScoringCategory.SENTIMENT.value
    assert 0 <= items[0].score <= 100
