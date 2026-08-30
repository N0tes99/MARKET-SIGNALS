"""Dated 8-K filing dates + lagged Yahoo quarterlies — no live Yahoo info."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pytest
from httpx import AsyncClient

from app.engines.runner_engine.backtest.pit import (
    build_dated_series,
    revenues_knowable_as_of,
    statement_knowable_date,
)
from app.engines.runner_engine.backtest.replay import evaluate_as_of
from app.engines.runner_engine.backtest.study import run_study
from app.engines.runner_engine.scoring.edgar import snapshot_as_of
from app.engines.runner_engine.scoring.yahoo_snapshot import (
    quarterly_revenue_series_from_frame,
)
from app.market_data.normalizer import STANDARD_COLUMNS


def _daily(closes: list[float], start: date = date(2020, 1, 1)) -> pd.DataFrame:
    rows = []
    origin = datetime(start.year, start.month, start.day, tzinfo=UTC)
    for i, close in enumerate(closes):
        px = float(close)
        rows.append(
            {
                "timestamp": origin + timedelta(days=i),
                "open": px,
                "high": px * 1.01,
                "low": px * 0.99,
                "close": px,
                "volume": 1_000.0 + i,
            }
        )
    return pd.DataFrame(rows, columns=STANDARD_COLUMNS)


def _winner_closes() -> list[float]:
    base = [10.0] * 90
    run = [10.0 * (1.012**i) for i in range(1, 161)]
    return base + run


def test_statement_uses_10q_filing_date_when_present() -> None:
    period = date(2020, 3, 31)
    filed = date(2020, 4, 20)
    assert statement_knowable_date(period, (filed,)) == filed
    assert statement_knowable_date(period, ()) == date(2020, 5, 15)


def test_quarterly_before_lag_is_not_knowable() -> None:
    series = (
        (date(2019, 6, 30), 50.0),
        (date(2019, 9, 30), 60.0),
        (date(2019, 12, 31), 80.0),
    )
    before = revenues_knowable_as_of(series, date(2020, 1, 20), ())
    after = revenues_knowable_as_of(series, date(2020, 2, 20), ())
    assert len(before) == 2
    assert len(after) == 3
    assert after[0] == 80.0


def test_8k_after_as_of_does_not_count() -> None:
    filings = ((date(2020, 6, 1), "8-K"),)
    early = snapshot_as_of("WIN", filings, date(2020, 5, 1))
    late = snapshot_as_of("WIN", filings, date(2020, 6, 2))
    assert early.eight_k_count == 0
    assert late.eight_k_count == 1
    assert late.latest_date == date(2020, 6, 1)


def test_dated_series_ignores_live_yahoo_info_fields() -> None:
    series = (
        (date(2019, 6, 30), 50.0),
        (date(2019, 9, 30), 60.0),
        (date(2019, 12, 31), 90.0),
    )
    dated = build_dated_series(
        "WIN",
        revenue_series=series,
        filings=((date(2020, 2, 20), "8-K"),),
    )
    blob = " ".join(
        " ".join(dim.factors) for snap in dated for dim in snap.dimensions.values()
    ).lower()
    assert "market cap" not in blob
    assert "analyst" not in blob
    assert "forward p/e" not in blob
    assert any(snap.dimensions["fundamental"].data_quality == "good" for snap in dated)
    assert any(
        "EDGAR 8-K" in line
        for snap in dated
        for line in snap.dimensions["catalyst"].factors
    )


def test_evaluate_as_of_fills_fund_only_after_knowable_date() -> None:
    df = _daily(_winner_closes(), start=date(2019, 10, 1))
    series = (
        (date(2019, 3, 31), 50.0),
        (date(2019, 6, 30), 60.0),
        (date(2020, 3, 31), 90.0),
    )
    dated = build_dated_series("WIN", revenue_series=series, filings=())
    before = evaluate_as_of(df, date(2020, 4, 1), dated_fundamentals=dated)
    after = evaluate_as_of(df, date(2020, 6, 1), dated_fundamentals=dated)
    assert before is not None and after is not None
    assert before.fundamentals_available is False
    assert after.fundamentals_available is True


def test_quarterly_series_keeps_period_end_dates() -> None:
    frame = pd.DataFrame(
        [[80.0, 100.0, 120.0]],
        index=["Total Revenue"],
        columns=["2025-10-31", "2026-01-31", "2026-04-30"],
    )
    series = quarterly_revenue_series_from_frame(frame)
    assert series[0] == (date(2026, 4, 30), 120.0)
    assert series[2] == (date(2025, 10, 31), 80.0)


@pytest.mark.asyncio
async def test_backtest_api_look_ahead_mentions_dated(client: AsyncClient, monkeypatch) -> None:
    frames = {"WIN": _daily(_winner_closes()), "SMH": _daily(_winner_closes())}
    dated = {
        "WIN": build_dated_series(
            "WIN",
            revenue_series=(
                (date(2019, 6, 30), 50.0),
                (date(2019, 9, 30), 60.0),
                (date(2019, 12, 31), 90.0),
            ),
            filings=((date(2020, 3, 1), "8-K"),),
        )
    }

    def _fake_cached(**kwargs):
        return run_study(
            frames,
            symbols=("WIN",),
            dated_fundamentals=dated,
            mode="dated_fundamentals",
        )

    monkeypatch.setattr("app.api.routes.runners.cached_live_study", _fake_cached)
    resp = await client.get("/api/v1/runners/backtest")
    assert resp.status_code == 200
    body = resp.json()
    look = body["look_ahead"].lower()
    assert "filing" in look
    assert "lagged" in look or "lag" in look
    assert "13f" in look
    assert "not a complete manager universe" in look
    assert "unused" in look
    assert body["mode"] == "dated_fundamentals"
    assert body["cases"][0]["hit_2x"] is True
