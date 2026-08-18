"""Crypto radar — Watch / Crowded / Running unit tests."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pandas as pd
import pytest
from httpx import AsyncClient

from app.engines.paper_agent.crypto_perp_v2 import V2_UNIVERSE
from app.engines.runner_engine.crypto_learn import (
    CryptoLearnCoefficients,
    get_crypto_learn_config,
)
from app.engines.runner_engine.crypto_radar import (
    CRYPTO_RADAR_UNIVERSE,
    clear_crypto_radar_cache,
    scan_crypto_radar,
    score_symbol,
)
from app.market_data.providers.bybit_derivatives import DerivativesDepth
from app.schemas.crypto_radar import CryptoRadarFeedResponse


class _Market:
    def __init__(self, mom_12h: float = 5.0, mom_20d: float = 12.0) -> None:
        self._mom_12h = mom_12h
        self._mom_20d = mom_20d

    def safe_get_ohlcv(self, symbol, timeframe, limit=96):
        if timeframe == "1h":
            lookback = 12
            target = self._mom_12h
            n = max(limit, lookback + 4)
        else:
            lookback = 20
            target = self._mom_20d
            n = max(limit, lookback + 4)
        start = 100.0
        end = start * (1.0 + target / 100.0)
        rows = []
        for i in range(n):
            # Flat history, then linear move over the measured window.
            if i < n - (lookback + 1):
                close = start
            else:
                j = i - (n - (lookback + 1))
                t = j / lookback
                close = start + (end - start) * t
            rows.append(
                {
                    "timestamp": datetime(2026, 8, 13, 0, 0, tzinfo=UTC),
                    "open": close,
                    "high": close * 1.01,
                    "low": close * 0.99,
                    "close": close,
                    "volume": 10.0,
                }
            )
        return pd.DataFrame(rows)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    clear_crypto_radar_cache()
    get_crypto_learn_config().reset(persist=False)
    yield
    clear_crypto_radar_cache()
    get_crypto_learn_config().reset(persist=False)


def _depth(*, funding: float = 0.001, oi_hist: list[float] | None = None) -> DerivativesDepth:
    return DerivativesDepth(
        symbol="SOL",
        funding_rate=funding,
        open_interest=1_000_000.0,
        mark_price=150.0,
        funding_history=[funding] * 8,
        oi_history=oi_hist or [100.0, 105.0],
        source="okx",
    )


def test_score_symbol_running_on_strong_momentum(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.runner_engine.crypto_radar.fetch_derivatives_depth",
        lambda symbol: _depth(funding=0.0002),
    )
    monkeypatch.setattr(
        "app.engines.runner_engine.crypto_radar.fetch_fear_greed",
        lambda: (45, "Neutral"),
    )
    cand = score_symbol(_Market(5.0, 18.0), "SOL")  # type: ignore[arg-type]
    assert cand.bucket == "running"
    assert cand.score >= 60.0
    assert cand.mom_12h_pct is not None


def test_score_symbol_crowded_on_extreme_funding(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.runner_engine.crypto_radar.fetch_derivatives_depth",
        lambda symbol: _depth(funding=0.0012, oi_hist=[100.0, 110.0]),
    )
    monkeypatch.setattr(
        "app.engines.runner_engine.crypto_radar.fetch_fear_greed",
        lambda: (55, "Neutral"),
    )
    cand = score_symbol(_Market(1.0, 2.0), "BTC")  # type: ignore[arg-type]
    assert cand.bucket == "crowded"
    assert cand.funding_bps == pytest.approx(12.0)
    assert cand.funding_source == "okx"


def test_score_symbol_watch_on_soft_setup(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.runner_engine.crypto_radar.fetch_derivatives_depth",
        lambda symbol: _depth(funding=0.0004),
    )
    monkeypatch.setattr(
        "app.engines.runner_engine.crypto_radar.fetch_fear_greed",
        lambda: (50, "Neutral"),
    )
    cand = score_symbol(_Market(2.0, 9.0), "ETH")  # type: ignore[arg-type]
    assert cand.bucket == "watch"


def test_scan_orders_by_score(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.runner_engine.crypto_radar.fetch_derivatives_depth",
        lambda symbol: _depth(funding=0.0002),
    )
    monkeypatch.setattr(
        "app.engines.runner_engine.crypto_radar.fetch_fear_greed",
        lambda: (40, "Fear"),
    )
    ideas = scan_crypto_radar(_Market(6.0, 16.0), symbols=("BTC", "ETH"), use_cache=False)  # type: ignore[arg-type]
    assert len(ideas) == 2
    assert ideas[0].score >= ideas[1].score


@pytest.mark.asyncio
async def test_crypto_radar_route(client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.runners.crypto_radar_lists",
        lambda: {
            "watch": [
                SimpleNamespace(
                    id="crypto-radar:ETH",
                    symbol="ETH",
                    bucket="watch",
                    score=58.0,
                    factors=["12h +2.0%"],
                    conflicts=[],
                    mom_12h_pct=2.0,
                    mom_20d_pct=9.0,
                    funding_bps=3.5,
                    oi_change_pct=1.0,
                    funding_source="okx",
                    mark_price=3000.0,
                    as_of=datetime.now(UTC),
                )
            ],
            "crowded": [],
            "running": [],
            "all": [
                SimpleNamespace(
                    id="crypto-radar:ETH",
                    symbol="ETH",
                    bucket="watch",
                    score=58.0,
                    factors=["12h +2.0%"],
                    conflicts=[],
                    mom_12h_pct=2.0,
                    mom_20d_pct=9.0,
                    funding_bps=3.5,
                    oi_change_pct=1.0,
                    funding_source="okx",
                    mark_price=3000.0,
                    as_of=datetime.now(UTC),
                )
            ],
        },
    )
    response = await client.get("/api/v1/runners/crypto")
    assert response.status_code == 200
    data = CryptoRadarFeedResponse.model_validate(response.json())
    assert data.symbols_scanned == 16
    assert len(data.universe) == 16
    assert data.coefficients_preset == "default"
    assert data.perp_momentum_n == 0
    assert len(data.watch) == 1
    assert data.watch[0].symbol == "ETH"
    assert data.funding_filled == 1


def test_universe_is_sixteen_aligned_names() -> None:
    assert len(V2_UNIVERSE) == 16
    assert CRYPTO_RADAR_UNIVERSE == V2_UNIVERSE
    for name in ("SUI", "ADA", "LTC", "DOT"):
        assert name in V2_UNIVERSE


def test_score_symbol_adds_basis_factor(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.runner_engine.crypto_radar.fetch_derivatives_depth",
        lambda symbol: _depth(funding=0.0002),
    )
    monkeypatch.setattr(
        "app.engines.runner_engine.crypto_radar.fetch_fear_greed",
        lambda: (45, "Neutral"),
    )

    class _SpotMarket(_Market):
        def get_ticker(self, symbol):
            return SimpleNamespace(price=148.5)

    cand = score_symbol(_SpotMarket(5.0, 18.0), "SOL")  # type: ignore[arg-type]
    assert cand.basis_pct is not None
    assert any(f.startswith("Basis ") for f in cand.factors)


def test_score_symbol_skips_basis_when_spot_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.runner_engine.crypto_radar.fetch_derivatives_depth",
        lambda symbol: _depth(funding=0.0002),
    )
    monkeypatch.setattr(
        "app.engines.runner_engine.crypto_radar.fetch_fear_greed",
        lambda: (45, "Neutral"),
    )
    cand = score_symbol(_Market(5.0, 18.0), "SOL")  # type: ignore[arg-type]
    assert cand.basis_pct is None
    assert not any(f.startswith("Basis ") for f in cand.factors)


def test_score_symbol_respects_coefficient_override(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.runner_engine.crypto_radar.fetch_derivatives_depth",
        lambda symbol: _depth(funding=0.0012, oi_hist=[100.0, 110.0]),
    )
    monkeypatch.setattr(
        "app.engines.runner_engine.crypto_radar.fetch_fear_greed",
        lambda: (55, "Neutral"),
    )
    get_crypto_learn_config().apply(
        CryptoLearnCoefficients(funding_extreme_bps=20.0, preset="test_override"),
        persist=False,
    )
    cand = score_symbol(_Market(1.0, 2.0), "BTC")  # type: ignore[arg-type]
    assert cand.bucket != "crowded"
    assert cand.funding_bps == pytest.approx(12.0)
