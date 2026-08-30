"""Radar Phase 6: OOS structure-threshold tune vs structure-only baseline."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest
from httpx import AsyncClient

from app.engines.runner_engine.backtest.dataset import (
    HOLDOUT_STUDY_SYMBOLS,
    PATTERN_STUDY_SYMBOLS,
    TRAIN_STUDY_SYMBOLS,
)
from app.engines.runner_engine.backtest.replay import walk_signals
from app.engines.runner_engine.backtest.study import StudyMetrics, replay_case
from app.engines.runner_engine.backtest.tune import (
    BASELINE_STRUCTURE_ACCUMULATION,
    STRUCTURE_ACCUMULATION_GRID,
    TuneGridRow,
    config_with_structure_accumulation,
    pick_train_winner,
    recommend_threshold,
    run_tune,
    score_metrics,
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


def _control_closes() -> list[float]:
    return [50.0 + 1.5 * ((i % 20) - 10) / 10.0 for i in range(220)]


def _row(
    threshold: float,
    *,
    train_score: float,
    holdout_score: float,
    holdout_fpr5: float | None = None,
    n_5x: int = 1,
    is_baseline: bool | None = None,
) -> TuneGridRow:
    holdout = StudyMetrics(
        n_5x=n_5x,
        false_positive_rate_5x=holdout_fpr5,
        false_positive_rate_2x=holdout_fpr5,
    )
    return TuneGridRow(
        structure_accumulation=threshold,
        is_baseline=(
            is_baseline if is_baseline is not None else threshold == BASELINE_STRUCTURE_ACCUMULATION
        ),
        train_score=train_score,
        holdout_score=holdout_score,
        train_metrics=StudyMetrics(),
        holdout_metrics=holdout,
    )


def test_famous_pattern_names_are_holdout_not_train() -> None:
    assert set(TRAIN_STUDY_SYMBOLS).isdisjoint(HOLDOUT_STUDY_SYMBOLS)
    assert HOLDOUT_STUDY_SYMBOLS == PATTERN_STUDY_SYMBOLS
    for symbol in PATTERN_STUDY_SYMBOLS:
        assert symbol not in TRAIN_STUDY_SYMBOLS


def test_score_prefers_precision_over_a_long_lead() -> None:
    good = StudyMetrics(
        n_5x=1,
        precision_5x=0.8,
        recall_5x=1.0,
        false_positive_rate_5x=0.2,
        median_lead_days_2x=80,
    )
    flashy = StudyMetrics(
        n_5x=1,
        precision_5x=0.4,
        recall_5x=1.0,
        false_positive_rate_5x=1.0,
        median_lead_days_2x=400,
    )
    assert score_metrics(good) > score_metrics(flashy)


def test_grid_picks_highest_train_score() -> None:
    rows = [
        _row(45.0, train_score=1.0, holdout_score=9.0),
        _row(55.0, train_score=1.2, holdout_score=8.0),
        _row(60.0, train_score=2.5, holdout_score=0.1),
        _row(70.0, train_score=2.0, holdout_score=7.0),
    ]
    assert pick_train_winner(rows).structure_accumulation == 60.0


def test_holdout_scores_do_not_change_train_pick() -> None:
    rows = [
        _row(45.0, train_score=3.0, holdout_score=0.1),
        _row(55.0, train_score=1.0, holdout_score=9.9),
        _row(70.0, train_score=2.0, holdout_score=8.0),
    ]
    assert pick_train_winner(rows).structure_accumulation == 45.0


def test_recommend_reverts_when_holdout_is_worse() -> None:
    rows = [
        _row(45.0, train_score=3.0, holdout_score=0.1, holdout_fpr5=1.0),
        _row(55.0, train_score=1.0, holdout_score=1.5, holdout_fpr5=0.4),
    ]
    recommended, accepted = recommend_threshold(rows)
    assert recommended == BASELINE_STRUCTURE_ACCUMULATION
    assert accepted is False


def test_recommend_keeps_train_pick_when_holdout_holds() -> None:
    rows = [
        _row(60.0, train_score=2.4, holdout_score=2.0, holdout_fpr5=0.3),
        _row(55.0, train_score=1.1, holdout_score=1.5, holdout_fpr5=0.4),
    ]
    recommended, accepted = recommend_threshold(rows)
    assert recommended == 60.0
    assert accepted is True


def test_recommend_rejects_higher_holdout_fpr() -> None:
    rows = [
        _row(45.0, train_score=3.0, holdout_score=2.0, holdout_fpr5=1.0),
        _row(55.0, train_score=1.0, holdout_score=1.5, holdout_fpr5=0.25),
    ]
    recommended, accepted = recommend_threshold(rows)
    assert recommended == BASELINE_STRUCTURE_ACCUMULATION
    assert accepted is False


def test_structure_gate_can_move_early_prints() -> None:
    df = _daily(_winner_closes())
    points = walk_signals(df, step=5)
    structs = [p.scores.structure for p in points]
    if not structs:
        pytest.skip("synthetic winner produced no walk points")
    lo, hi = min(structs), max(structs)
    low = replay_case(
        "WIN",
        df,
        config=config_with_structure_accumulation(max(0.0, lo - 5.0)),
        step=5,
    )
    high = replay_case(
        "WIN",
        df,
        config=config_with_structure_accumulation(min(100.0, hi + 5.0)),
        step=5,
    )
    assert low.first_early is not None
    assert high.first_early is None


def test_run_tune_does_not_fit_on_holdout_symbols() -> None:
    frames = {
        "WIN": _daily(_winner_closes()),
        "FLAT": _daily(_control_closes()),
        "FAMOUS": _daily(_winner_closes()),
        "SMH": _daily(_control_closes()),
    }
    report = run_tune(
        frames,
        train_symbols=("WIN", "FLAT"),
        holdout_symbols=("FAMOUS",),
        grid=STRUCTURE_ACCUMULATION_GRID,
    )
    assert "FAMOUS" not in report.train_symbols
    assert report.train_symbols == ("WIN", "FLAT")
    assert report.holdout_symbols == ("FAMOUS",)
    assert report.applied_to_live is False
    assert report.train_winner_structure_accumulation in STRUCTURE_ACCUMULATION_GRID
    assert report.recommended_structure_accumulation in {
        report.train_winner_structure_accumulation,
        BASELINE_STRUCTURE_ACCUMULATION,
    }
    assert "not applied to live" in report.note.lower()
    assert "famous" in report.note.lower()
    assert "13f" in report.note.lower()
    assert "not a complete manager universe" in report.note.lower()


def test_run_tune_rejects_overlap() -> None:
    with pytest.raises(ValueError, match="overlap"):
        run_tune(
            {},
            train_symbols=("SMCI",),
            holdout_symbols=("SMCI", "KO"),
        )


def test_tune_module_does_not_import_grade_optimizer() -> None:
    text = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "engines"
        / "runner_engine"
        / "backtest"
        / "tune.py"
    ).read_text(encoding="utf-8")
    assert "WeightOptimizer" not in text
    assert "app.scoring.optimizer" not in text


@pytest.mark.asyncio
async def test_tune_api_uses_injected_frames(client: AsyncClient, monkeypatch) -> None:
    frames = {
        "WIN": _daily(_winner_closes()),
        "FLAT": _daily(_control_closes()),
        "FAMOUS": _daily(_winner_closes()),
        "SMH": _daily(_control_closes()),
    }

    def _fake_cached(**kwargs):
        return run_tune(
            frames,
            train_symbols=("WIN", "FLAT"),
            holdout_symbols=("FAMOUS",),
        )

    monkeypatch.setattr("app.api.routes.runners.cached_live_tune", _fake_cached)
    resp = await client.get("/api/v1/runners/tune")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "structure_threshold_grid"
    assert body["applied_to_live"] is False
    assert body["baseline_structure_accumulation"] == 55.0
    assert set(body["train_symbols"]) == {"WIN", "FLAT"}
    assert body["holdout_symbols"] == ["FAMOUS"]
    assert "out-of-sample" in body["note"].lower()
    assert "famous" in body["note"].lower()
    assert "13f" in body["note"].lower()
    assert any(r["is_baseline"] for r in body["rows"])
    assert "precision_5x" in body["baseline_holdout"]
    assert "precision_5x" in body["recommended_holdout"]
