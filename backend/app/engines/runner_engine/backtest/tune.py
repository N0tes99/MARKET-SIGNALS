"""Phase 6: out-of-sample structure-threshold tune vs structure-only baseline.

Famous pattern-study names are holdout and never pick the threshold. Modifier
weights (discovery / theme / inst / squeeze) do not apply on structure-only
replay — those dims are missing until dated fundamentals exist. Live Radar
defaults are not changed here.

This is not Surface 1 grade-weight tuning (`/api/v1/tuning`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import UTC, datetime

import pandas as pd

from app.engines.runner_engine.backtest.dataset import (
    HOLDOUT_STUDY_SYMBOLS,
    TRAIN_STUDY_SYMBOLS,
    DatedFundamentals,
)
from app.engines.runner_engine.backtest.multiples import label_multiples
from app.engines.runner_engine.backtest.replay import walk_signals
from app.engines.runner_engine.backtest.study import (
    CaseResult,
    FrameFetcher,
    StudyMetrics,
    aggregate_metrics,
    case_from_labels,
    load_study_frames,
)
from app.engines.runner_engine.config import RUNNER_PHASE, RunnerConfig, default_runner_config
from app.engines.runner_engine.stage import classify
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

STRUCTURE_ACCUMULATION_GRID: tuple[float, ...] = (45.0, 50.0, 55.0, 60.0, 65.0, 70.0)
BASELINE_STRUCTURE_ACCUMULATION = 55.0

TUNE_NOTE = (
    "Out-of-sample structure-accumulation grid vs structure-only baseline (55). "
    "Famous pattern-study names are holdout and never pick the threshold. "
    "Modifier weights unused until dated fundamentals exist. "
    "Not applied to live Radar."
)


@dataclass(frozen=True)
class TuneGridRow:
    """One structure_accumulation setting on train + holdout."""

    structure_accumulation: float
    is_baseline: bool
    train_score: float
    holdout_score: float
    train_metrics: StudyMetrics
    holdout_metrics: StudyMetrics


@dataclass
class TuneReport:
    """Phase 6 v0 OOS tune. Live defaults stay at 55."""

    phase: str
    mode: str
    generated_at: datetime
    note: str
    train_symbols: tuple[str, ...]
    holdout_symbols: tuple[str, ...]
    grid: tuple[float, ...]
    baseline_structure_accumulation: float
    train_winner_structure_accumulation: float
    recommended_structure_accumulation: float
    applied_to_live: bool
    holdout_accepts_tuned: bool
    rows: list[TuneGridRow]


_CACHE: TTLCache[TuneReport] = TTLCache(ttl_seconds=1800.0)


@dataclass(frozen=True)
class _WalkBundle:
    labels: object
    points: list
    frame: pd.DataFrame


def config_with_structure_accumulation(
    threshold: float,
    *,
    base: RunnerConfig | None = None,
) -> RunnerConfig:
    """Fresh config; do not mutate ``default_runner_config()`` internals."""
    cfg = base or default_runner_config()
    return replace(
        cfg,
        stages=replace(cfg.stages, structure_accumulation=float(threshold)),
    )


def score_metrics(metrics: StudyMetrics) -> float:
    """Train objective. Prefer 5× when the split has a 5× label."""
    if metrics.n_5x > 0:
        prec = metrics.precision_5x
        rec = metrics.recall_5x
        fpr = metrics.false_positive_rate_5x
    else:
        prec = metrics.precision_2x
        rec = metrics.recall_2x
        fpr = metrics.false_positive_rate_2x
    p = float(prec) if prec is not None else 0.0
    r = float(rec) if rec is not None else 0.0
    f = float(fpr) if fpr is not None else 0.0
    lead = float(metrics.median_lead_days_2x) if metrics.median_lead_days_2x is not None else 0.0
    return 2.0 * p + r - f + min(lead, 400.0) / 4000.0


def primary_fpr(metrics: StudyMetrics) -> float | None:
    if metrics.n_5x > 0:
        return metrics.false_positive_rate_5x
    return metrics.false_positive_rate_2x


def pick_train_winner(rows: list[TuneGridRow]) -> TuneGridRow:
    """Argmax train score. Ties break toward the live baseline (55)."""
    if not rows:
        raise ValueError("empty structure-accumulation grid")
    best = max(r.train_score for r in rows)
    tied = [r for r in rows if r.train_score == best]
    return min(
        tied,
        key=lambda r: (
            abs(r.structure_accumulation - BASELINE_STRUCTURE_ACCUMULATION),
            r.structure_accumulation,
        ),
    )


def holdout_accepts_tuned(tuned: TuneGridRow, baseline: TuneGridRow) -> bool:
    """Keep the train pick only if holdout is not worse than baseline."""
    if tuned.structure_accumulation == baseline.structure_accumulation:
        return True
    if tuned.holdout_score < baseline.holdout_score:
        return False
    t_fpr = primary_fpr(tuned.holdout_metrics)
    b_fpr = primary_fpr(baseline.holdout_metrics)
    if t_fpr is not None and b_fpr is not None:
        return t_fpr <= b_fpr
    return True


def recommend_threshold(
    rows: list[TuneGridRow],
    *,
    baseline_threshold: float = BASELINE_STRUCTURE_ACCUMULATION,
) -> tuple[float, bool]:
    """Return (recommended threshold, whether holdout accepted the train pick)."""
    baseline_row = next(r for r in rows if r.structure_accumulation == baseline_threshold)
    winner = pick_train_winner(rows)
    accepted = holdout_accepts_tuned(winner, baseline_row)
    if accepted:
        return winner.structure_accumulation, accepted
    return baseline_threshold, False


def _first_prints(points: list, cfg: RunnerConfig) -> tuple[object, object, object]:
    first_early = first_ignition = first_running = None
    for point in points:
        _stage, _signal, watch = classify(
            point.scores,
            cfg,
            fundamentals_available=point.fundamentals_available,
        )
        if first_early is None and watch == "early":
            first_early = point.as_of
        if first_ignition is None and watch == "ignition":
            first_ignition = point.as_of
        if first_running is None and watch == "running":
            first_running = point.as_of
    return first_early, first_ignition, first_running


def _metrics_for(
    symbols: tuple[str, ...],
    bundles: dict[str, _WalkBundle],
    cfg: RunnerConfig,
) -> StudyMetrics:
    cases: list[CaseResult] = []
    for symbol in symbols:
        key = symbol.upper()
        bundle = bundles.get(key)
        if bundle is None:
            cases.append(CaseResult(symbol=key, bars=0, error="missing ohlcv"))
            continue
        first_early, first_ignition, first_running = _first_prints(bundle.points, cfg)
        cases.append(
            case_from_labels(
                key,
                bundle.frame,
                bundle.labels,
                first_early=first_early,
                first_ignition=first_ignition,
                first_running=first_running,
            )
        )
    return aggregate_metrics(cases)


def _walk_bundles(
    frames: dict[str, pd.DataFrame],
    symbols: tuple[str, ...],
    *,
    dated_fundamentals: dict[str, tuple[DatedFundamentals, ...]] | None,
    step: int,
) -> dict[str, _WalkBundle]:
    bench = frames.get("SMH")
    if bench is None or bench.empty:
        bench = frames.get("SPY")
    out: dict[str, _WalkBundle] = {}
    for symbol in symbols:
        key = symbol.upper()
        df = frames.get(key)
        if df is None or df.empty:
            continue
        try:
            labels = label_multiples(df)
            points = walk_signals(
                df,
                bench=bench,
                dated_fundamentals=(dated_fundamentals or {}).get(key, ()),
                step=step,
            )
        except Exception:
            logger.exception("runner_tune walk failed for %s", key)
            continue
        out[key] = _WalkBundle(labels=labels, points=points, frame=df)
    return out


def run_tune(
    frames: dict[str, pd.DataFrame],
    *,
    train_symbols: tuple[str, ...] = TRAIN_STUDY_SYMBOLS,
    holdout_symbols: tuple[str, ...] = HOLDOUT_STUDY_SYMBOLS,
    grid: tuple[float, ...] = STRUCTURE_ACCUMULATION_GRID,
    dated_fundamentals: dict[str, tuple[DatedFundamentals, ...]] | None = None,
    step: int = 5,
    mode: str = "structure_threshold_grid",
) -> TuneReport:
    """Grid-search ``structure_accumulation`` on train; confirm on holdout."""
    overlap = set(s.upper() for s in train_symbols) & set(s.upper() for s in holdout_symbols)
    if overlap:
        raise ValueError(f"train/holdout overlap: {sorted(overlap)}")

    wanted = tuple(dict.fromkeys((*train_symbols, *holdout_symbols)))
    bundles = _walk_bundles(
        frames,
        wanted,
        dated_fundamentals=dated_fundamentals,
        step=step,
    )

    rows: list[TuneGridRow] = []
    for threshold in grid:
        cfg = config_with_structure_accumulation(threshold)
        train_metrics = _metrics_for(train_symbols, bundles, cfg)
        holdout_metrics = _metrics_for(holdout_symbols, bundles, cfg)
        rows.append(
            TuneGridRow(
                structure_accumulation=float(threshold),
                is_baseline=float(threshold) == BASELINE_STRUCTURE_ACCUMULATION,
                train_score=round(score_metrics(train_metrics), 4),
                holdout_score=round(score_metrics(holdout_metrics), 4),
                train_metrics=train_metrics,
                holdout_metrics=holdout_metrics,
            )
        )

    recommended, accepted = recommend_threshold(rows)
    winner = pick_train_winner(rows)
    return TuneReport(
        phase=RUNNER_PHASE,
        mode=mode,
        generated_at=datetime.now(UTC),
        note=TUNE_NOTE,
        train_symbols=tuple(s.upper() for s in train_symbols),
        holdout_symbols=tuple(s.upper() for s in holdout_symbols),
        grid=tuple(float(x) for x in grid),
        baseline_structure_accumulation=BASELINE_STRUCTURE_ACCUMULATION,
        train_winner_structure_accumulation=winner.structure_accumulation,
        recommended_structure_accumulation=recommended,
        applied_to_live=False,
        holdout_accepts_tuned=accepted,
        rows=rows,
    )


def cached_live_tune(
    *,
    fetcher: FrameFetcher | None = None,
    train_symbols: tuple[str, ...] = TRAIN_STUDY_SYMBOLS,
    holdout_symbols: tuple[str, ...] = HOLDOUT_STUDY_SYMBOLS,
) -> TuneReport:
    """TTL-cached live Yahoo 5y structure-threshold tune."""

    def _build() -> TuneReport:
        symbols = tuple(dict.fromkeys((*train_symbols, *holdout_symbols)))
        frames = load_study_frames(symbols, fetcher=fetcher)
        return run_tune(
            frames,
            train_symbols=train_symbols,
            holdout_symbols=holdout_symbols,
        )

    if fetcher is not None:
        return _build()
    return _CACHE.get_or_set("tune_v0_structure_gate", _build)
