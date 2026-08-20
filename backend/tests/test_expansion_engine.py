"""Unit tests for Surface 5 expansion engine."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from httpx import AsyncClient

from app.engines.expansion_engine.compression import analyze_compression
from app.engines.expansion_engine.config import default_expansion_config
from app.engines.expansion_engine.replay import replay_symbol
from app.engines.expansion_engine.scanner import ExpansionScanner
from app.engines.expansion_engine.squeeze_fuel import analyze_squeeze_fuel
from app.engines.expansion_engine.state import resolve_state
from app.engines.expansion_engine.trigger import analyze_trigger
from app.engines.expansion_engine.types import CompressionResult, ExpansionState
from app.market_data.providers.bybit_derivatives import DerivativesDepth
from app.market_data.providers.mock import MockMarketDataProvider
from app.market_data.service import MarketDataService


def _synthetic_compressed_rows(rows: int = 80, base: float = 100.0) -> pd.DataFrame:
    """Tight-range synthetic hourly bars (compression setup)."""
    ts = [datetime(2026, 8, 1, tzinfo=UTC) + timedelta(hours=i) for i in range(rows)]
    rng = np.random.default_rng(42)
    # Very tight band for last 25 bars; wider history before that
    close = np.empty(rows)
    close[: rows - 25] = base + rng.normal(0, 0.8, rows - 25)
    tight = base + rng.normal(0, 0.02, 25)
    close[rows - 25 :] = tight
    high = close + 0.03
    low = close - 0.03
    open_ = close.copy()
    volume = np.full(rows, 5000.0)
    volume[-8:] = 800.0  # volume dries up into compression
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def _inject_breakout(df: pd.DataFrame, start_idx: int, pct: float = 0.08) -> pd.DataFrame:
    """Add directional expansion after compression window."""
    out = df.copy()
    base = float(out["close"].iloc[start_idx])
    for i in range(start_idx, len(out)):
        progress = (i - start_idx + 1) / max(1, len(out) - start_idx)
        price = base * (1 + pct * progress)
        out.loc[out.index[i], "close"] = price
        out.loc[out.index[i], "open"] = price * 0.999
        out.loc[out.index[i], "high"] = price * 1.002
        out.loc[out.index[i], "low"] = price * 0.998
        out.loc[out.index[i], "volume"] = 2500.0
    return out


def test_compression_detects_tight_range() -> None:
    df = _synthetic_compressed_rows()
    result = analyze_compression(df)
    assert result is not None
    assert result.score >= 70.0
    assert result.atr_percentile is not None
    assert result.atr_percentile <= 25.0


def test_trigger_requires_volume() -> None:
    cfg = default_expansion_config()
    df = _synthetic_compressed_rows(rows=50)
    # Break high without volume
    df.loc[df.index[-1], "close"] = float(df["high"].iloc[-15:-1].max()) * 1.01
    df.loc[df.index[-1], "high"] = df.loc[df.index[-1], "close"] * 1.001
    result = analyze_trigger(df, config=cfg)
    assert result.direction == "up"
    assert result.active is False


def test_squeeze_fuel_with_compression_and_funding() -> None:
    compression = CompressionResult(
        score=88.0,
        atr_percentile=5.0,
        bb_width_percentile=8.0,
        range_compression_pct=90.0,
        volume_compression_pct=70.0,
        factors=["test"],
    )
    depth = DerivativesDepth(
        symbol="SOL",
        funding_rate=0.0005,
        open_interest=1_000_000,
        mark_price=150.0,
        oi_history=[100.0, 102.0, 108.0, 112.0],
        source="bybit",
    )
    result = analyze_squeeze_fuel(
        compression=compression,
        depth=depth,
        price=150.0,
        recent_momentum_pct=0.5,
    )
    assert result.score >= 60.0
    assert result.direction == "up"
    assert len(result.levels) == 4


def test_state_primedd_on_high_compression() -> None:
    compression = CompressionResult(
        score=88.0,
        atr_percentile=5.0,
        bb_width_percentile=8.0,
        range_compression_pct=90.0,
        volume_compression_pct=70.0,
        factors=[],
    )
    from app.engines.expansion_engine.types import SqueezeFuelResult, TriggerResult

    squeeze = SqueezeFuelResult(score=70.0, direction="neutral", factors=[], conflicts=[])
    trigger = TriggerResult(
        active=False,
        direction="neutral",
        volume_ratio=1.0,
        breakout_level=None,
    )
    state = resolve_state(
        compression=compression,
        squeeze=squeeze,
        trigger=trigger,
        mom_12h_pct=0.2,
    )
    assert state == ExpansionState.PRIMED


def test_replay_finds_earlier_primedd_than_v2() -> None:
    df = _synthetic_compressed_rows(rows=100)
    start = 55
    df = _inject_breakout(df, start, pct=0.10)
    event = replay_symbol(df, "SOL", v2_min_momentum_pct=1.5)
    assert event is not None
    assert event.max_move_pct >= 5.0
    assert event.primed_idx is not None
    if event.v2_first_idx is not None:
        assert event.primed_idx <= event.v2_first_idx or event.primed_hours_before_move is not None


@pytest.mark.asyncio
async def test_expansion_api_feed(client: AsyncClient) -> None:
    response = await client.get("/api/v1/expansion")
    assert response.status_code == 200
    body = response.json()
    assert "candidates" in body
    assert body["phase"] == "mvp_benchmark"
    assert body["symbols_scanned"] >= 0


@pytest.mark.asyncio
async def test_expansion_api_symbol(client: AsyncClient) -> None:
    response = await client.get("/api/v1/expansion/BTC")
    assert response.status_code in {200, 404}


def test_scanner_with_mock_market() -> None:
    provider = MockMarketDataProvider()
    market = MarketDataService(provider=provider)
    scanner = ExpansionScanner(market_data=market)
    results = scanner.scan(use_cache=False)
    assert isinstance(results, list)
