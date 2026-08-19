"""CME Yahoo futures scanner — score, classify, route shape, null-safe fields."""

from __future__ import annotations

import time
from datetime import UTC, date, datetime
from threading import Event

import pandas as pd
import pytest
from httpx import AsyncClient

from app.engines.runner_engine.cme_futures import (
    _CACHE,
    CME_FUTURES_UNIVERSE,
    CmeFuturesRow,
    classify_bucket,
    clear_cme_futures_cache,
    scan_cme_futures,
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
        raise AssertionError("CME last comes from fast_info or daily bars, not get_ticker")

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
def _clear_cache(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CME_FUTURES_DISK_CACHE_PATH", str(tmp_path / "cme_board.json"))
    monkeypatch.setattr(
        "app.engines.runner_engine.cme_futures.fetch_cot_snapshot",
        lambda symbol: None,
    )
    clear_cme_futures_cache()
    yield
    clear_cme_futures_cache()


def _universe_cache_key() -> str:
    return ",".join(spec.symbol for spec in CME_FUTURES_UNIVERSE)


def _stale_row(*, last: float = 1111.0) -> CmeFuturesRow:
    now = datetime.now(UTC)
    return CmeFuturesRow(
        id="cme-futures:ES=F",
        symbol="ES=F",
        name="E-mini S&P 500",
        group="index",
        bucket="quiet",
        score=41.0,
        last=last,
        as_of=now,
    )


def _wait_until_idle(key: str, timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _, _, refreshing, _ = _CACHE.meta(key)
        if not refreshing:
            return
        time.sleep(0.05)


def _quote(
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
    assert row.cot_effect is None


def test_score_symbol_cot_weakens_crowded_long(monkeypatch) -> None:
    from app.market_data.providers.cftc_cot import CotSnapshot, SCORE_TILT

    monkeypatch.setattr(
        "app.engines.runner_engine.cme_futures.fetch_yahoo_futures_quote",
        lambda symbol: _quote(),
    )
    plain = score_symbol(_Market(2.5, 8.0), "ES=F")  # type: ignore[arg-type]
    snap = CotSnapshot(
        symbol="ES=F",
        market_code="13874A",
        book="tff",
        report_date=date(2026, 8, 11),
        spec_long=500_000,
        spec_short=100_000,
        spec_net=400_000,
        open_interest=2_119_506,
        cot_index=92.0,
    )
    monkeypatch.setattr(
        "app.engines.runner_engine.cme_futures.fetch_cot_snapshot",
        lambda symbol: snap,
    )
    crowded = score_symbol(_Market(2.5, 8.0), "ES=F")  # type: ignore[arg-type]
    assert crowded.cot_effect == "weaken"
    assert crowded.cot_index == pytest.approx(92.0)
    assert crowded.score == pytest.approx(plain.score - SCORE_TILT)
    assert any("crowded long" in item for item in crowded.conflicts)


def test_score_symbol_weekly_cot_oi_when_yahoo_missing(monkeypatch) -> None:
    from app.market_data.providers.cftc_cot import CotSnapshot

    monkeypatch.setattr(
        "app.engines.runner_engine.cme_futures.fetch_yahoo_futures_quote",
        lambda symbol: _quote(open_interest=None),
    )
    monkeypatch.setattr(
        "app.engines.runner_engine.cme_futures.fetch_cot_snapshot",
        lambda symbol: CotSnapshot(
            symbol="ES=F",
            market_code="13874A",
            book="tff",
            report_date=date(2026, 8, 11),
            spec_long=205_744,
            spec_short=486_190,
            spec_net=-280_446,
            open_interest=2_119_506,
            cot_index=18.0,
        ),
    )
    row = score_symbol(_Market(2.5, 8.0), "ES=F")  # type: ignore[arg-type]
    assert row.open_interest == pytest.approx(2_119_506)
    assert row.cot_effect == "strengthen"
    assert any("Weekly COT OI" in item for item in row.factors)


def test_score_symbol_null_oi_and_expiry_safe(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.runner_engine.cme_futures.fetch_yahoo_futures_quote",
        lambda symbol: _quote(
            last=None,
            change_pct=None,
            volume=None,
            open_interest=None,
            expire=None,
        ),
    )
    row = score_symbol(_Market(0.3, 1.2, bar_volume=70_000.0), "CL=F")  # type: ignore[arg-type]
    assert row.symbol == "CL=F"
    assert row.open_interest is None
    assert row.expiry is None
    assert row.last is not None
    assert row.last > 0
    assert row.change_pct is not None
    assert row.volume is not None
    assert row.bucket in {"trending", "extended", "quiet"}
    assert 0.0 <= row.score <= 100.0


@pytest.mark.asyncio
async def test_futures_board_route(client: AsyncClient, monkeypatch) -> None:
    now = datetime.now(UTC)
    monkeypatch.setattr(
        "app.api.routes.futures.build_cme_futures_board",
        lambda **kwargs: CmeFuturesBoardSchema(
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


def test_scan_serves_stale_without_waiting_on_yahoo(monkeypatch) -> None:
    key = _universe_cache_key()
    stale = _stale_row(last=1111.0)
    _CACHE.seed_stale(key, [stale])

    started = Event()

    def _slow_score(market, symbol, **kwargs):
        started.set()
        time.sleep(0.12)
        return stale

    monkeypatch.setattr("app.engines.runner_engine.cme_futures.score_symbol", _slow_score)

    t0 = time.perf_counter()
    rows = scan_cme_futures()
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.1
    assert rows[0].last == pytest.approx(1111.0)
    assert started.wait(timeout=2.0)
    _wait_until_idle(key)
    _, fresh, refreshing, _ = _CACHE.meta(key)
    assert fresh is True
    assert refreshing is False


def test_scan_cold_miss_does_not_block_on_yahoo(monkeypatch) -> None:
    key = _universe_cache_key()
    started = Event()
    fresh_row = _stale_row(last=2222.0)

    def _slow_score(market, symbol, **kwargs):
        started.set()
        time.sleep(0.12)
        return fresh_row

    monkeypatch.setattr("app.engines.runner_engine.cme_futures.score_symbol", _slow_score)

    t0 = time.perf_counter()
    rows = scan_cme_futures()
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.1
    assert rows == []
    assert started.wait(timeout=2.0)
    _wait_until_idle(key)
    cached, fresh, refreshing, _ = _CACHE.meta(key)
    assert fresh is True
    assert refreshing is False
    assert cached is not None
    assert cached[0].last == pytest.approx(2222.0)


def test_scan_sync_true_writes_fresh_cache(monkeypatch) -> None:
    key = _universe_cache_key()
    fresh_row = _stale_row(last=3333.0)
    monkeypatch.setattr(
        "app.engines.runner_engine.cme_futures.score_symbol",
        lambda market, symbol, **kwargs: fresh_row,
    )
    rows = scan_cme_futures(sync=True)
    assert rows[0].last == pytest.approx(3333.0)
    _, fresh, refreshing, _ = _CACHE.meta(key)
    assert fresh is True
    assert refreshing is False


@pytest.mark.asyncio
async def test_futures_board_serves_stale_without_waiting(
    client: AsyncClient, monkeypatch
) -> None:
    key = _universe_cache_key()
    stale = _stale_row(last=1111.0)
    _CACHE.seed_stale(key, [stale])
    started = Event()

    def _slow_score(market, symbol, **kwargs):
        started.set()
        time.sleep(0.12)
        return stale

    monkeypatch.setattr("app.engines.runner_engine.cme_futures.score_symbol", _slow_score)

    t0 = time.perf_counter()
    response = await client.get("/api/v1/futures/board")
    elapsed = time.perf_counter() - t0
    assert response.status_code == 200
    assert elapsed < 0.2
    data = CmeFuturesBoardSchema.model_validate(response.json())
    assert data.rows[0].last == pytest.approx(1111.0)
    assert started.wait(timeout=2.0)
    _wait_until_idle(key)

