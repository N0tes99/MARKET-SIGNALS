"""Yahoo EPS surprise overlay for Radar catalyst."""

from datetime import date

import pandas as pd

from app.engines.runner_engine.scoring.yahoo_dims import score_catalyst
from app.engines.runner_engine.scoring.yahoo_snapshot import (
    YahooRunnerSnapshot,
    empty_yahoo_snapshot,
    eps_surprise_from_frame,
)


def test_eps_surprise_skips_future_and_uses_newest_print() -> None:
    frame = pd.DataFrame(
        {
            "EPS Estimate": [0.40, 0.42, 0.50],
            "Reported EPS": [0.48, 0.40, None],
            "Surprise(%)": [20.0, -4.8, None],
        },
        index=pd.to_datetime(["2026-05-15", "2026-08-20", "2026-11-12"]),
    )
    when, surprise, streak = eps_surprise_from_frame(
        frame, today=date(2026, 8, 27)
    )
    assert when == date(2026, 8, 20)
    assert surprise is not None and surprise < 0
    assert streak == 0


def test_eps_beat_streak_counts_consecutive() -> None:
    frame = pd.DataFrame(
        {
            "EPS Estimate": [0.30, 0.32, 0.34],
            "Reported EPS": [0.36, 0.35, 0.40],
            "Surprise(%)": [20.0, 9.4, 17.6],
        },
        index=pd.to_datetime(["2026-02-15", "2026-05-15", "2026-08-20"]),
    )
    when, surprise, streak = eps_surprise_from_frame(
        frame, today=date(2026, 8, 27)
    )
    assert when == date(2026, 8, 20)
    assert surprise is not None and surprise > 15
    assert streak == 3


def test_catalyst_from_eps_beat_without_earnings_date() -> None:
    snap = YahooRunnerSnapshot(
        symbol="CRDO",
        fetched_ok=True,
        eps_surprise_pct=18.0,
        eps_surprise_date=date(2026, 8, 20),
        eps_beat_streak=3,
    )
    dim = score_catalyst(snap, today=date(2026, 8, 27))
    assert dim.data_quality == "good"
    assert dim.score > 50
    assert any("EPS surprise +18.0%" in line for line in dim.factors)
    assert any("3-quarter beat streak" in line for line in dim.factors)


def test_catalyst_eps_miss_is_conflict() -> None:
    snap = YahooRunnerSnapshot(
        symbol="CRDO",
        fetched_ok=True,
        eps_surprise_pct=-12.0,
        eps_surprise_date=date(2026, 8, 20),
    )
    dim = score_catalyst(snap, today=date(2026, 8, 27))
    assert any("Large EPS miss" in line for line in dim.conflicts)
    assert dim.score < 50


def test_empty_snapshot_still_missing_without_surprise() -> None:
    dim = score_catalyst(empty_yahoo_snapshot("CRDO"), today=date(2026, 8, 27))
    assert dim.data_quality == "missing"
