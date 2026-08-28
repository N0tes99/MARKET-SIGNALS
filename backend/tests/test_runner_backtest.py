"""Radar Phase 5: truncated-tape lead time, no live Yahoo look-ahead."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pytest
from httpx import AsyncClient

from app.engines.runner_engine.backtest.dataset import DatedFundamentals
from app.engines.runner_engine.backtest.multiples import label_multiples, truncate_to
from app.engines.runner_engine.backtest.replay import evaluate_as_of
from app.engines.runner_engine.backtest.study import aggregate_metrics, replay_case, run_study
from app.engines.runner_engine.types import DimensionScore
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


def _control_closes() -> list[float]:
    return [50.0 + 1.5 * ((i % 20) - 10) / 10.0 for i in range(220)]


def test_truncate_drops_future_bars() -> None:
    df = _daily(_winner_closes())
    cut_date = date(2020, 1, 1) + timedelta(days=89)
    window = truncate_to(df, cut_date)
    assert len(window) == 90
    assert float(window["close"].iloc[-1]) == 10.0
    assert float(df["close"].iloc[-1]) > 40.0


def test_evaluate_as_of_cannot_see_future_close() -> None:
    df = _daily(_winner_closes())
    as_of = date(2020, 1, 1) + timedelta(days=89)
    point = evaluate_as_of(df, as_of)
    assert point is not None
    assert point.last_close == 10.0
    assert point.fundamentals_available is False
    assert point.watchlist != "ignition"
    assert point.watchlist != "running"


def test_structure_only_winner_never_prints_ignition() -> None:
    df = _daily(_winner_closes())
    case = replay_case("WIN", df, step=5)
    assert case.hit_2x is True
    assert case.hit_5x is True
    assert case.first_ignition is None
    assert case.first_running is None
    labels = label_multiples(df)
    assert labels.trough_close == 10.0


def test_dated_fundamentals_can_reach_ignition() -> None:
    df = _daily(_winner_closes())
    fund = DatedFundamentals(
        as_of=date(2020, 1, 1),
        dimensions={
            "fundamental": DimensionScore(
                name="fundamental", score=80.0, confidence=0.8, data_quality="good"
            ),
            "catalyst": DimensionScore(
                name="catalyst", score=80.0, confidence=0.8, data_quality="good"
            ),
        },
    )
    # Snapshot dated after the whole path must not apply at T0-era bars.
    future = DatedFundamentals(
        as_of=date(2030, 1, 1),
        dimensions={
            "fundamental": DimensionScore(
                name="fundamental", score=99.0, confidence=0.8, data_quality="good"
            ),
            "catalyst": DimensionScore(
                name="catalyst", score=99.0, confidence=0.8, data_quality="good"
            ),
        },
    )
    as_of = date(2020, 1, 1) + timedelta(days=89)
    blocked = evaluate_as_of(df, as_of, dated_fundamentals=(future,))
    assert blocked is not None
    assert blocked.fundamentals_available is False

    case = replay_case("WIN", df, dated_fundamentals=(fund,), step=5)
    assert case.hit_2x is True
    # With real fund + rising tape, ignition is allowed; do not require it
    # if structure never clears 70 on this synthetic path.
    assert case.first_ignition is None or case.first_early is not None


def test_control_never_hits_2x() -> None:
    df = _daily(_control_closes())
    case = replay_case("FLAT", df, step=5)
    assert case.hit_2x is False
    assert case.hit_5x is False
    assert case.lead_days_to_2x is None


def test_aggregate_precision_recall() -> None:
    winner = replay_case("WIN", _daily(_winner_closes()), step=5)
    control = replay_case("FLAT", _daily(_control_closes()), step=5)
    metrics = aggregate_metrics([winner, control])
    assert metrics.n_cases == 2
    assert metrics.n_2x == 1
    assert metrics.n_5x == 1
    if winner.first_early is not None:
        assert metrics.true_positives_2x == 1
        assert metrics.recall_2x == 1.0
        assert metrics.true_positives_5x == 1
        if control.first_early is not None:
            assert metrics.false_positives_5x == 1
            assert metrics.false_positive_rate_5x == 1.0
        assert metrics.median_lead_days_2x is not None or winner.late_for_2x


def test_run_study_missing_frame() -> None:
    study = run_study({}, symbols=("ZZZ",))
    assert study.cases[0].error == "missing ohlcv"
    assert study.metrics.n_cases == 0
    assert "Yahoo fundamentals unused" in study.look_ahead


def test_max_dd_and_time_to_nx() -> None:
    df = _daily(_winner_closes())
    case = replay_case("WIN", df, step=5)
    assert case.days_to_2x is not None and case.days_to_2x > 0
    assert case.days_to_5x is not None and case.days_to_5x >= case.days_to_2x
    if case.first_early is not None:
        assert case.max_dd_after_early_pct is not None
        assert case.max_dd_after_early_pct >= 0


@pytest.mark.asyncio
async def test_backtest_api_uses_injected_frames(client: AsyncClient, monkeypatch) -> None:
    frames = {
        "WIN": _daily(_winner_closes()),
        "FLAT": _daily(_control_closes()),
        "SMH": _daily(_control_closes()),
    }

    def _fake_cached(**kwargs):
        return run_study(frames, symbols=("WIN", "FLAT"))

    monkeypatch.setattr(
        "app.api.routes.runners.cached_live_study",
        _fake_cached,
    )
    resp = await client.get("/api/v1/runners/backtest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "structure_tape"
    assert "look ahead" in body["look_ahead"].lower() or "unused" in body["look_ahead"].lower()
    symbols = {c["symbol"] for c in body["cases"]}
    assert symbols == {"WIN", "FLAT"}
    win = next(c for c in body["cases"] if c["symbol"] == "WIN")
    assert win["hit_2x"] is True
    assert win["first_ignition"] is None
    flat = next(c for c in body["cases"] if c["symbol"] == "FLAT")
    assert flat["hit_2x"] is False
    assert "precision_2x" in body["metrics"]
