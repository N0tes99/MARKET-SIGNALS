"""Perps board API tests."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.engines.paper_agent.perps_board import _BOARD_CACHE, build_perps_board
from app.market_data.providers.bybit_derivatives import DerivativesDepth
from app.market_data.providers.coinglass import LiquidationSnapshot
from app.schemas.perps import PerpsBoardSchema


@pytest.fixture(autouse=True)
def _clear_board_cache() -> None:
    _BOARD_CACHE.clear()
    yield
    _BOARD_CACHE.clear()


def test_build_perps_board_funding_and_empty_liqs(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.perps_board.settings.coinglass_api_key",
        "",
    )
    monkeypatch.setattr(
        "app.engines.paper_agent.perps_board.fetch_derivatives_depth",
        lambda symbol, timeout=2.0: DerivativesDepth(
            symbol=symbol,
            funding_rate=0.0008 if symbol == "BTC" else -0.0002,
            open_interest=1_000_000.0,
            mark_price=100.0,
            funding_history=[0.0001, 0.0002, 0.0003, 0.0008],
            oi_history=[100.0, 110.0],
            source="bybit",
        ),
    )
    monkeypatch.setattr(
        "app.engines.paper_agent.perps_board.fetch_aggregated_liquidations",
        lambda symbol, **kwargs: None,
    )

    class _Scanner:
        def scan_feed(self, **_kwargs):
            return [
                SimpleNamespace(
                    id="1",
                    symbol="BTC",
                    setup_type="funding_extreme",
                    direction_bias="short",
                    confidence=70.0,
                    factors=["Funding +8 bps"],
                    trade_state_hint="WATCH",
                ),
                SimpleNamespace(
                    id="2",
                    symbol="ETH",
                    setup_type="trend_break",
                    direction_bias="long",
                    confidence=80.0,
                    factors=["ignore me"],
                    trade_state_hint="WATCH",
                ),
            ]

    board = build_perps_board(symbols=("BTC", "ETH"), setup_scanner=_Scanner())  # type: ignore[arg-type]
    assert isinstance(board, PerpsBoardSchema)
    assert board.symbols_scanned == 2
    assert board.funding_filled == 2
    assert board.liquidations_configured is False
    assert board.liquidations_filled == 0
    assert "COINGLASS" in board.liquidations_note.upper() or "Coinglass" in board.liquidations_note
    assert board.funding[0].symbol == "BTC"  # highest |bps|
    assert board.funding[0].funding_bps == pytest.approx(8.0)
    assert board.funding_source == "bybit"
    assert len(board.ideas) == 1
    assert board.ideas[0].setup_type == "funding_extreme"
    assert all(row.coinglass_url for row in board.liquidations)


def test_build_perps_board_with_liquidations(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.perps_board.settings.coinglass_api_key",
        "test-key",
    )
    monkeypatch.setattr(
        "app.engines.paper_agent.perps_board.fetch_derivatives_depth",
        lambda symbol, timeout=2.0: DerivativesDepth(
            symbol=symbol,
            funding_rate=0.0001,
            open_interest=500_000.0,
            mark_price=50.0,
            funding_history=[0.0001] * 6,
            oi_history=[100.0, 95.0],
            source="bybit",
        ),
    )
    monkeypatch.setattr(
        "app.engines.paper_agent.perps_board.fetch_aggregated_liquidations",
        lambda symbol, **kwargs: LiquidationSnapshot(
            symbol=symbol,
            long_usd=40_000_000,
            short_usd=10_000_000,
            interval="4h",
        ),
    )
    board = build_perps_board(symbols=("SOL",), setup_scanner=None)
    assert board.liquidations_configured is True
    assert board.liquidations_filled == 1
    assert board.liquidations[0].available is True
    assert board.liquidations[0].long_usd == 40_000_000
    assert "longs flushed" in board.liquidations[0].description


@pytest.mark.asyncio
async def test_perps_board_route(client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.perps.build_perps_board",
        lambda setup_scanner=None: PerpsBoardSchema(
            as_of=datetime.now(UTC),
            universe=["BTC"],
            funding=[],
            liquidations=[],
            ideas=[],
            liquidations_configured=False,
            liquidations_note="test",
            symbols_scanned=1,
            funding_filled=0,
            liquidations_filled=0,
        ),
    )
    response = await client.get("/api/v1/perps/board")
    assert response.status_code == 200
    data = response.json()
    assert data["symbols_scanned"] == 1
    assert data["funding_source"] == "okx|bybit"
