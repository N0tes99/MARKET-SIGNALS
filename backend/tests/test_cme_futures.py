"""CME Yahoo futures scanner — score, classify, route shape, null-safe fields."""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

import pandas as pd
import pytest
from httpx import AsyncClient

from app.engines.runner_engine.cme_futures import (
    CME_FUTURES_UNIVERSE,
    classify_bucket,
    clear_cme_futures_cache,
    score_symbol,
)
from app.engines.runner_engine.scoring.yahoo_futures_quote import YahooFuturesQuote
from app.market_data.symbols import FUTURES_SYMBOLS
from app.schemas.cme_futures import CmeFuturesBoardSchema


class _Market:
    def __init__(
        self,
        mom_12h: float = 2.5,
        mom_20d: float = 8.0,
        last: float = 5400.0,
        bar_volume: float = 180_000.0,
        avg_volume: float = 100_000.0,
    ) -> None:
        self._mom_12h = mom_12h
        self._mom_20d = mom_20d
        self._last = last
        self._bar_volume = bar_volume
        self._avg_volume = avg_volume

    def get_ticker(self, symbol):
        return SimpleNamespace(price=self._last)

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
            if i < n - (lookback + 1):
                close = start
                volume = self._avg_volume
            else:
                j = i - (n - (lookback + 1))
                t = j / lookback
                close = start + (end - start) * t
                volume = self._bar_volume
            rows.append(
                {
                    "timestamp": datetime(2026, 8, 13, 0, 0, tzinfo=UTC),
                    "open": close,
                    "high": close * 1.01,
                    "low": close * 0.99,
                    "close": close,
                    "volume": volume,
                }
            )
        return pd.DataFrame(rows)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    clear_cme_futures_cache()
    yield
    clear_cme_futures_cache()


def _quote(
    *,
    change_pct: float | None = 0.42,
    volume: float | None = 180_000.0,
    open_interest: float | None = 2_100_000.0,
    expire: date | None = date(2026, 9, 18),
    last: float | None = 5400.0,
) -> YahooFuturesQuote:
    return YahooFuturesQuote(
        symbol="ES=F",
        fetched_ok=True,
        last=last,
        change_pct=change_pct,
        volume=volume,
        open_interest=open_interest,
        expire_date=expire,
    )


def test_universe_is_twenty_four_named_contracts() -> None:
    assert len(FUTURES_SYMBOLS) == 24
    assert len(CME_FUTURES_UNIVERSE) == 24
    assert tuple(c.symbol for c in CME_FUTURES_UNIVERSE) == FUTURES_SYMBOLS
    for name in ("ES=F", "NQ=F", "CL=F", "GC=F", "ZN=F", "6E=F", "ZC=F", "BTC=F"):
        assert name in FUTURES_SYMBOLS
    groups = {c.group.value for c in CME_FUTURES_UNIVERSE}
    assert groups == {"index", "energy", "metals", "rates", "fx", "grains", "crypto"}


def test_classify_trending_on_strong_momentum() -> None:
    assert (
        classify_bucket(score=68.0, mom_12h=2.5, mom_20d=8.0) == "trending"
    )


def test_classify_extended_on_stretched_20d() -> None:
    assert (
        classify_bucket(score=57.0, mom_12h=0.2, mom_20d=15.0) == "extended"
    )


def test_classify_quiet_on_flat_tape() -> None:
    assert classify_bucket(score=49.0, mom_12h=0.2, mom_20d=1.0) == "quiet"


def test_score_symbol_trending(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.runner_engine.cme_futures.fetch_yahoo_futures_quote",
        lambda symbol: _quote(),
    )
    row = score_symbol(_Market(2.5, 8.0), "ES=F")  # type: ignore[arg-type]
    assert row.symbol == "ES=F"
    assert row.name == "E-mini S&P 500"
    assert row.group == "index"
    assert row.bucket == "trending"
    assert row.score >= 55.0
    assert row.last == pytest.approx(5400.0)
    assert row.open_interest == pytest.approx(2_100_000.0)
    assert row.expiry == date(2026, 9, 18)
    assert row.mom_12h_pct is not None


def test_score_symbol_null_oi_and_expiry_safe(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.runner_engine.cme_futures.fetch_yahoo_futures_quote",
        lambda symbol: _quote(open_interest=None, expire=None, change_pct=None),
    )
    row = score_symbol(_Market(0.3, 1.2, bar_volume=70_000.0), "CL=F")  # type: ignore[arg-type]
    assert row.symbol == "CL=F"
    assert row.open_interest is None
    assert row.expiry is None
    assert row.change_pct is None
    assert row.bucket in {"trending", "extended", "quiet"}
    assert 0.0 <= row.score <= 100.0


@pytest.mark.asyncio
async def test_futures_board_route(client: AsyncClient, monkeypatch) -> None:
    now = datetime.now(UTC)
    monkeypatch.setattr(
        "app.api.routes.futures.build_cme_futures_board",
        lambda: CmeFuturesBoardSchema(
            rows=[
                {
                    "id": "cme-futures:ES=F",
                    "symbol": "ES=F",
                    "name": "E-mini S&P 500",
                    "group": "index",
                    "bucket": "trending",
                    "score": 71.0,
                    "last": 5400.0,
                    "change_pct": 0.42,
                    "volume": 180000.0,
                    "open_interest": None,
                    "expiry": None,
                    "mom_12h_pct": 2.1,
                    "mom_20d_pct": 7.4,
                    "relative_volume": 1.6,
                    "factors": ["12h +2.1%"],
                    "conflicts": [],
                    "as_of": now,
                }
            ],
            scanned_at=now,
            symbols_scanned=24,
            universe=[
                {"symbol": spec.symbol, "name": spec.name, "group": spec.group.value}
                for spec in CME_FUTURES_UNIVERSE
            ],
            source="yahoo",
        ),
    )
    response = await client.get("/api/v1/futures/board")
    assert response.status_code == 200
    data = CmeFuturesBoardSchema.model_validate(response.json())
    assert data.symbols_scanned == 24
    assert len(data.universe) == 24
    assert data.universe[0].symbol == "ES=F"
    assert data.universe[0].name
    assert data.universe[0].group == "index"
    assert data.rows[0].symbol == "ES=F"
    assert data.rows[0].open_interest is None
    assert data.rows[0].expiry is None
    assert data.source == "yahoo"
