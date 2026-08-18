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


class _Resp:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._payload


class _RoutedClient:
    def __init__(self, routes: dict[str, _Resp]) -> None:
        self.routes = routes

    def get(self, url: str, params=None, **kwargs):
        for key, resp in self.routes.items():
            if key in url:
                return resp
        return _Resp(404, {})


def _reset_liq_caches(monkeypatch) -> None:
    cache_mod = __import__("app.utils.ttl_cache", fromlist=["TTLCache"])
    monkeypatch.setattr(
        "app.market_data.providers.coinglass._LIQ_CACHE",
        cache_mod.TTLCache(ttl_seconds=1.0),
    )
    monkeypatch.setattr(
        "app.market_data.providers.coinglass._CTVAL_CACHE",
        cache_mod.TTLCache(ttl_seconds=1.0),
    )


def _okx_liq_payload() -> dict:
    # 10 contracts * 0.01 BTC * 50_000 = $5_000 long
    # 20 contracts * 0.01 BTC * 51_000 = $10_200 short
    ts = 1_787_060_000_000
    return {
        "code": "0",
        "data": [
            {
                "instId": "BTC-USDT-SWAP",
                "uly": "BTC-USDT",
                "details": [
                    {
                        "posSide": "long",
                        "side": "sell",
                        "sz": "10",
                        "bkPx": "50000",
                        "ts": str(ts),
                    },
                    {
                        "posSide": "short",
                        "side": "buy",
                        "sz": "20",
                        "bkPx": "51000",
                        "ts": str(ts + 60_000),
                    },
                ],
            }
        ],
    }


def test_fetch_liquidations_okx_without_coinglass_key(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.market_data.providers.coinglass.settings.coinglass_api_key",
        "",
    )
    _reset_liq_caches(monkeypatch)
    client = _RoutedClient(
        {
            "liquidation-orders": _Resp(200, _okx_liq_payload()),
            "instruments": _Resp(
                200,
                {
                    "code": "0",
                    "data": [{"instId": "BTC-USDT-SWAP", "ctVal": "0.01"}],
                },
            ),
            "bybit.com": _Resp(403, {"error": "blocked"}),
        }
    )
    monkeypatch.setattr(
        "app.market_data.providers.coinglass.shared_client",
        lambda **_kwargs: client,
    )
    snap = fetch_aggregated_liquidations("BTC")
    assert snap is not None
    assert snap.long_usd == 5_000.0
    assert snap.short_usd == 10_200.0
    assert snap.interval == "okx"
    score, desc = score_liquidations(snap)
    assert score < 50
    assert "shorts flushed" in desc


def test_fetch_liquidations_empty_or_geo_blocked(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.market_data.providers.coinglass.settings.coinglass_api_key",
        "",
    )
    _reset_liq_caches(monkeypatch)
    client = _RoutedClient(
        {
            "liquidation-orders": _Resp(403, {"error": "blocked"}),
            "instruments": _Resp(403, {"error": "blocked"}),
            "bybit.com": _Resp(403, {"error": "blocked"}),
        }
    )
    monkeypatch.setattr(
        "app.market_data.providers.coinglass.shared_client",
        lambda **_kwargs: client,
    )
    assert fetch_aggregated_liquidations("BTC") is None

    _reset_liq_caches(monkeypatch)
    empty = _RoutedClient(
        {
            "liquidation-orders": _Resp(200, {"code": "0", "data": []}),
            "instruments": _Resp(
                200,
                {"code": "0", "data": [{"ctVal": "0.01"}]},
            ),
            "recent-liquidation": _Resp(200, {"retCode": 0, "result": {"list": []}}),
            "market/liquidation": _Resp(200, {"retCode": 0, "result": {"list": []}}),
        }
    )
    monkeypatch.setattr(
        "app.market_data.providers.coinglass.shared_client",
        lambda **_kwargs: empty,
    )
    assert fetch_aggregated_liquidations("ETH") is None


def test_fetch_liquidations_bybit_when_okx_empty(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.market_data.providers.coinglass.settings.coinglass_api_key",
        "",
    )
    _reset_liq_caches(monkeypatch)
    ts = 1_787_060_000_000
    client = _RoutedClient(
        {
            "liquidation-orders": _Resp(200, {"code": "0", "data": []}),
            "recent-liquidation": _Resp(
                200,
                {
                    "retCode": 0,
                    "result": {
                        "list": [
                            {"T": ts, "S": "Buy", "v": "0.5", "p": "50000"},
                            {"T": ts + 60_000, "S": "Sell", "v": "0.2", "p": "51000"},
                        ]
                    },
                },
            ),
        }
    )
    monkeypatch.setattr(
        "app.market_data.providers.coinglass.shared_client",
        lambda **_kwargs: client,
    )
    snap = fetch_aggregated_liquidations("BTC")
    assert snap is not None
    assert snap.long_usd == 25_000.0
    assert snap.short_usd == 10_200.0
    assert snap.interval == "bybit"


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
        def get(self, *args, **kwargs):
            return _Resp()

    monkeypatch.setattr(
        "app.market_data.providers.coinglass.shared_client",
        lambda **_kwargs: _Client(),
    )
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
