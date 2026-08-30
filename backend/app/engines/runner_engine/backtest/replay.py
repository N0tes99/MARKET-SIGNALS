"""Point-in-time Radar classify — truncated daily bars only, no live Yahoo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from app.engines.opportunity_engine.equity_options.momentum import compute_momentum
from app.engines.runner_engine.backtest.dataset import OFFSET_DAYS, DatedFundamentals
from app.engines.runner_engine.backtest.multiples import bar_date, days_between, truncate_to
from app.engines.runner_engine.compose import compose_runner_scores
from app.engines.runner_engine.config import RunnerConfig, default_runner_config
from app.engines.runner_engine.stage import classify, classify_alert_gate
from app.engines.runner_engine.types import (
    AlertGate,
    DimensionScore,
    RunnerScores,
    RunnerSignalType,
    RunnerStage,
    RunnerTapeSnapshot,
    WatchlistBucket,
)
from app.engines.sector_rs_engine.engine import period_return, score_relative_strength
from app.utils.scoring_helpers import clamp_score


def _missing(name: str) -> DimensionScore:
    return DimensionScore(
        name=name,
        score=50.0,
        confidence=0.35,
        data_quality="missing",
    )


def _structure_from_frames(
    ohlcv: pd.DataFrame,
    bench: pd.DataFrame | None,
) -> tuple[DimensionScore, RunnerTapeSnapshot]:
    tape = RunnerTapeSnapshot()
    snap = compute_momentum(ohlcv)
    if snap is None:
        return _missing("structure"), tape

    tape.ret_20d_pct = snap.ret_20d_pct
    tape.relative_volume = snap.relative_volume
    rs_score = 50.0
    if bench is not None and not bench.empty:
        asset_ret = period_return(ohlcv["close"])
        bench_ret = period_return(bench["close"])
        if asset_ret is not None and bench_ret is not None:
            rel = asset_ret - bench_ret
            rs_score, tone = score_relative_strength(rel)
            tape.rs_pct = rel
            tape.rs_benchmark = "bench"
            snap.factors.append(f"RS α {rel:+.1f}% — {tone}")

    blended = clamp_score(0.70 * snap.momentum_score + 0.30 * rs_score)
    tape.structure_score = blended
    return (
        DimensionScore(
            name="structure",
            score=blended,
            confidence=0.85,
            factors=[f"Momentum {snap.momentum_score:.0f}", *snap.factors[:4]],
            conflicts=list(snap.conflicts[:4]),
            data_quality="good",
        ),
        tape,
    )


def _fundamentals_for(
    as_of: date,
    snapshots: tuple[DatedFundamentals, ...],
) -> dict[str, DimensionScore]:
    eligible = [s for s in snapshots if s.as_of <= as_of]
    if not eligible:
        return {}
    latest = max(eligible, key=lambda s: s.as_of)
    return dict(latest.dimensions)


@dataclass
class ReplayPoint:
    """One as-of classify. Last close is the truncated bar, not the future."""

    as_of: date
    last_close: float | None
    bars_used: int
    stage: RunnerStage
    signal_type: RunnerSignalType
    watchlist: WatchlistBucket
    alert_gate: AlertGate
    scores: RunnerScores
    fundamentals_available: bool
    offset_days: int | None = None


def evaluate_as_of(
    ohlcv: pd.DataFrame,
    as_of: date,
    *,
    bench: pd.DataFrame | None = None,
    config: RunnerConfig | None = None,
    dated_fundamentals: tuple[DatedFundamentals, ...] = (),
) -> ReplayPoint | None:
    """Classify using only bars dated on or before ``as_of``.

    Live Yahoo snippets are never fetched here. Fundamentals apply only when a
    dated snapshot exists with as_of <= the bar. Institutional replay is 13F
    search (incomplete), never live Yahoo ownership.
    """
    cfg = config or default_runner_config()
    window = truncate_to(ohlcv, as_of)
    if window.empty or len(window) < 55:
        return None
    bench_window = truncate_to(bench, as_of) if bench is not None else None
    structure, _tape = _structure_from_frames(window, bench_window)
    fund = _fundamentals_for(as_of, dated_fundamentals)
    dimensions: dict[str, DimensionScore] = {
        "fundamental": fund.get("fundamental", _missing("fundamental")),
        "catalyst": fund.get("catalyst", _missing("catalyst")),
        "structure": structure,
        "asymmetry": fund.get("asymmetry", _missing("asymmetry")),
        "discovery_gap": fund.get("discovery_gap", _missing("discovery_gap")),
        "theme_bottleneck": fund.get("theme_bottleneck", _missing("theme_bottleneck")),
        "institutional_accum": fund.get("institutional_accum", _missing("institutional_accum")),
        "short_squeeze_potential": fund.get(
            "short_squeeze_potential", _missing("short_squeeze_potential")
        ),
    }
    scores = compose_runner_scores(dimensions, cfg)
    fundamentals_available = dimensions["fundamental"].data_quality != "missing"
    stage, signal, watchlist = classify(
        scores,
        cfg,
        fundamentals_available=fundamentals_available,
    )
    gate = classify_alert_gate(scores, watchlist, cfg.alerts)
    last_close = float(window["close"].iloc[-1])
    return ReplayPoint(
        as_of=bar_date(window["timestamp"].iloc[-1]),
        last_close=last_close,
        bars_used=len(window),
        stage=stage,
        signal_type=signal,
        watchlist=watchlist,
        alert_gate=gate,
        scores=scores,
        fundamentals_available=fundamentals_available,
    )


def walk_signals(
    ohlcv: pd.DataFrame,
    *,
    bench: pd.DataFrame | None = None,
    config: RunnerConfig | None = None,
    dated_fundamentals: tuple[DatedFundamentals, ...] = (),
    step: int = 5,
) -> list[ReplayPoint]:
    """Walk forward on truncated prefixes. ``step`` keeps runtime bounded."""
    if ohlcv is None or len(ohlcv) < 55:
        return []
    points: list[ReplayPoint] = []
    last_idx = len(ohlcv) - 1
    for idx in range(54, last_idx + 1, max(1, step)):
        as_of = bar_date(ohlcv["timestamp"].iloc[idx])
        point = evaluate_as_of(
            ohlcv,
            as_of,
            bench=bench,
            config=config,
            dated_fundamentals=dated_fundamentals,
        )
        if point is not None:
            points.append(point)
    if last_idx % max(1, step) != 0:
        as_of = bar_date(ohlcv["timestamp"].iloc[last_idx])
        if not points or points[-1].as_of != as_of:
            point = evaluate_as_of(
                ohlcv,
                as_of,
                bench=bench,
                config=config,
                dated_fundamentals=dated_fundamentals,
            )
            if point is not None:
                points.append(point)
    return points


def offset_snapshots(
    ohlcv: pd.DataFrame,
    t0: date,
    *,
    bench: pd.DataFrame | None = None,
    config: RunnerConfig | None = None,
    dated_fundamentals: tuple[DatedFundamentals, ...] = (),
    offsets: tuple[int, ...] = OFFSET_DAYS,
) -> list[ReplayPoint]:
    """Classify at T-180 … T0 relative to an outcome date (usually first 2×)."""
    from datetime import timedelta

    out: list[ReplayPoint] = []
    for days in offsets:
        as_of = t0 - timedelta(days=days)
        point = evaluate_as_of(
            ohlcv,
            as_of,
            bench=bench,
            config=config,
            dated_fundamentals=dated_fundamentals,
        )
        if point is None:
            continue
        point.offset_days = -days if days else 0
        out.append(point)
    return out


def first_list_date(points: list[ReplayPoint], watch: WatchlistBucket) -> date | None:
    for point in points:
        if point.watchlist == watch:
            return point.as_of
    return None


def lead_days(signal_on: date | None, outcome_on: date | None) -> int | None:
    """Positive = signal before outcome. None if either side is missing or late."""
    delta = days_between(signal_on, outcome_on)
    if delta is None or delta < 0:
        return None
    return delta
