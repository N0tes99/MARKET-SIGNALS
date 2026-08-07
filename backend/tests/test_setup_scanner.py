"""Unit tests for opportunity setup scanners."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.engines.opportunity_engine.scanner import (
    SetupScanner,
    scan_basis_rich,
    scan_funding_extreme,
    scan_liq_flush,
)
from app.market_data.providers.bybit_derivatives import DerivativesDepth
from app.market_data.providers.coinglass import LiquidationSnapshot
from app.market_data.providers.mock import MockMarketDataProvider
from app.market_data.service import MarketDataService


def _as_of() -> datetime:
    return datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


def test_funding_extreme_crowded_long() -> None:
    depth = DerivativesDepth(
        symbol="BTC",
        funding_rate=0.0012,  # 12 bps
        open_interest=1_000_000,
        mark_price=60_000,
        funding_history=[0.0002] * 10,
        oi_history=[100.0, 102.0, 105.0, 110.0],  # rising ~10%
        source="bybit",
    )
    idea = scan_funding_extreme("BTC", depth, _as_of())
    assert idea is not None
    assert idea.setup_type == "funding_extreme"
    assert idea.direction_bias == "short"
    assert idea.trade_state_hint in {"IGNORE", "WATCH"}
    assert idea.trade_state_hint != "EXECUTE"
    assert 0 <= idea.confidence <= 100
    assert any("Funding" in f for f in idea.factors)


def test_funding_extreme_skips_neutral() -> None:
    depth = DerivativesDepth(
        symbol="BTC",
        funding_rate=0.0001,
        open_interest=1_000_000,
        mark_price=60_000,
        oi_history=[100.0, 101.0],
        source="bybit",
    )
    assert scan_funding_extreme("BTC", depth, _as_of()) is None


def test_funding_extreme_missing_depth() -> None:
    assert scan_funding_extreme("BTC", None, _as_of()) is None


def test_liq_flush_longs() -> None:
    snap = LiquidationSnapshot(
        symbol="ETH",
        long_usd=80_000_000,
        short_usd=15_000_000,
        interval="4h",
    )
    idea = scan_liq_flush("ETH", snap, _as_of())
    assert idea is not None
    assert idea.setup_type == "liq_flush"
    assert idea.direction_bias == "long"
    assert idea.trade_state_hint in {"IGNORE", "WATCH"}


def test_liq_flush_balanced_or_small_skips() -> None:
    balanced = LiquidationSnapshot("BTC", long_usd=6_000_000, short_usd=5_500_000)
    assert scan_liq_flush("BTC", balanced, _as_of()) is None
    tiny = LiquidationSnapshot("BTC", long_usd=900_000, short_usd=100_000)
    assert scan_liq_flush("BTC", tiny, _as_of()) is None
    assert scan_liq_flush("BTC", None, _as_of()) is None


def test_basis_rich_mark_above_spot() -> None:
    depth = DerivativesDepth(
        symbol="SOL",
        funding_rate=0.0001,
        open_interest=500_000,
        mark_price=100.25,
        source="binance",
    )
    idea = scan_basis_rich("SOL", depth, spot_price=100.0, as_of=_as_of())
    assert idea is not None
    assert idea.setup_type == "basis_rich"
    assert idea.direction_bias == "short"
    assert any("Basis" in f for f in idea.factors)


def test_basis_rich_requires_both_prices() -> None:
    depth = DerivativesDepth(symbol="SOL", mark_price=100.0, source="bybit")
    assert scan_basis_rich("SOL", depth, spot_price=None, as_of=_as_of()) is None
    assert scan_basis_rich("SOL", None, spot_price=100.0, as_of=_as_of()) is None


def test_scanner_equity_empty() -> None:
    scanner = SetupScanner(MarketDataService(provider=MockMarketDataProvider()))
    assert scanner.scan("AAPL") == []


def test_scanner_soft_fails_missing_feeds(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.opportunity_engine.scanner.fetch_derivatives_depth",
        lambda symbol: None,
    )
    monkeypatch.setattr(
        "app.engines.opportunity_engine.scanner.fetch_aggregated_liquidations",
        lambda symbol: None,
    )
    # Fresh cache so monkeypatch applies
    from app.utils.ttl_cache import TTLCache

    monkeypatch.setattr(
        "app.engines.opportunity_engine.scanner._SCAN_CACHE",
        TTLCache(ttl_seconds=1.0),
    )

    scanner = SetupScanner(MarketDataService(provider=MockMarketDataProvider()))
    ideas = scanner.scan("BTC")
    assert ideas == []


@pytest.mark.asyncio
async def test_get_asset_setups_endpoint(client: AsyncClient, monkeypatch) -> None:
    """GET /assets/{symbol}/setups returns a valid envelope (soft-fail empty ok)."""
    from app.core.service_dependencies import get_setup_scanner
    from app.engines.opportunity_engine.scanner import SetupScanner
    from app.main import app
    from app.utils.ttl_cache import TTLCache

    monkeypatch.setattr(
        "app.engines.opportunity_engine.scanner.fetch_derivatives_depth",
        lambda symbol: None,
    )
    monkeypatch.setattr(
        "app.engines.opportunity_engine.scanner.fetch_aggregated_liquidations",
        lambda symbol: None,
    )
    monkeypatch.setattr(
        "app.engines.opportunity_engine.scanner._SCAN_CACHE",
        TTLCache(ttl_seconds=1.0),
    )

    scanner = SetupScanner(MarketDataService(provider=MockMarketDataProvider()))
    app.dependency_overrides[get_setup_scanner] = lambda: scanner
    try:
        response = await client.get("/api/v1/assets/BTC/setups")
    finally:
        app.dependency_overrides.pop(get_setup_scanner, None)

    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "BTC"
    assert isinstance(data["setups"], list)
    assert "scanned_at" in data
    for idea in data["setups"]:
        assert idea["trade_state_hint"] in {"IGNORE", "WATCH"}
        assert idea["setup_type"] in {"funding_extreme", "liq_flush", "basis_rich"}


@pytest.mark.asyncio
async def test_get_asset_setups_unknown_symbol(client: AsyncClient) -> None:
    response = await client.get("/api/v1/assets/ZZZ/setups")
    assert response.status_code == 404
