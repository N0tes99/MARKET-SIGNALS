"""Coinglass liquidations + on-chain enrichment tests."""

from app.engines.onchain_engine import (
    blend_activity_with_change,
    score_btc_mempool,
    score_difficulty_progress,
)
from app.market_data.providers.bybit_derivatives import score_derivatives_composite
from app.market_data.providers.coinglass import (
    LiquidationSnapshot,
    fetch_aggregated_liquidations,
    score_liquidations,
)
from app.scoring.weights import ScoringCategory


def test_score_liquidations_long_flush_bullish() -> None:
    snap = LiquidationSnapshot("BTC", long_usd=80_000_000, short_usd=20_000_000)
    score, desc = score_liquidations(snap)
    assert score > 50
    assert "longs flushed" in desc


def test_score_liquidations_short_flush_cautious() -> None:
    snap = LiquidationSnapshot("ETH", long_usd=10_000_000, short_usd=40_000_000)
    score, desc = score_liquidations(snap)
    assert score < 50
    assert "shorts flushed" in desc


def test_score_derivatives_blends_liquidations() -> None:
    base, _ = score_derivatives_composite(0.0001, [0.0001] * 6, 0.0)
    with_liq, desc = score_derivatives_composite(
        0.0001,
        [0.0001] * 6,
        0.0,
        liquidation_score=70.0,
        liquidation_note="Liqs 4h — longs flushed",
    )
    assert with_liq > base
    assert "longs flushed" in desc


def test_fetch_liquidations_skips_without_key(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.market_data.providers.coinglass.settings.coinglass_api_key",
        "",
    )
    assert fetch_aggregated_liquidations("BTC") is None


def test_fetch_liquidations_parses_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.market_data.providers.coinglass.settings.coinglass_api_key",
        "test-key",
    )
    monkeypatch.setattr(
        "app.market_data.providers.coinglass._LIQ_CACHE",
        __import__("app.utils.ttl_cache", fromlist=["TTLCache"]).TTLCache(ttl_seconds=1.0),
    )

    class _Resp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "code": "0",
                "msg": "success",
                "data": [
                    {
                        "time": 1,
                        "aggregated_long_liquidation_usd": 1_000_000,
                        "aggregated_short_liquidation_usd": 4_000_000,
                    },
                    {
                        "time": 2,
                        "aggregated_long_liquidation_usd": 2_000_000,
                        "aggregated_short_liquidation_usd": 3_000_000,
                    },
                ],
            }

    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, *args, **kwargs):
            return _Resp()

    monkeypatch.setattr("app.market_data.providers.coinglass.httpx.Client", _Client)
    snap = fetch_aggregated_liquidations("BTC", limit=2)
    assert snap is not None
    assert snap.long_usd == 3_000_000
    assert snap.short_usd == 7_000_000


def test_difficulty_and_activity_blend() -> None:
    late, _ = score_difficulty_progress(95)
    early, _ = score_difficulty_progress(5)
    assert early > late
    calm, _ = score_btc_mempool(3.0)
    blended, desc = blend_activity_with_change(44.0, "elevated turnover", 12.0)
    assert blended < 44.0
    assert "surge" in desc
    _ = calm
    assert ScoringCategory.ON_CHAIN.value == "On-Chain"
