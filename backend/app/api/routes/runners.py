"""Surface 4 Runner Detection API endpoints."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.service_dependencies import get_learning_engine, get_runner_scanner
from app.engines.runner_engine.backtest.dataset import STUDY_SYMBOLS
from app.engines.runner_engine.backtest.study import cached_live_study
from app.engines.runner_engine.backtest.tune import cached_live_tune
from app.engines.runner_engine.config import RUNNER_PHASE, default_runner_config
from app.engines.runner_engine.crypto_learn import (
    get_crypto_learn_coefficients,
    perp_momentum_expectancy,
)
from app.engines.runner_engine.crypto_radar import (
    CRYPTO_RADAR_UNIVERSE,
    CryptoRadarCandidate,
    crypto_radar_lists,
)
from app.engines.runner_engine.scanner import RunnerScanner
from app.engines.runner_engine.types import RunnerCandidate
from app.schemas.crypto_radar import CryptoRadarCandidateSchema, CryptoRadarFeedResponse
from app.schemas.runners import (
    RunnerBacktestCaseSchema,
    RunnerBacktestMetricsSchema,
    RunnerBacktestResponse,
    RunnerBacktestSnapshotSchema,
    RunnerCandidateSchema,
    RunnerConfigMetaResponse,
    RunnerDetailResponse,
    RunnerFeedResponse,
    RunnerListsResponse,
    RunnerScoresSchema,
    RunnerTuneGridRowSchema,
    RunnerTuneResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _fundamentals_counts(candidates: list[RunnerCandidate]) -> tuple[int, int]:
    filled = sum(1 for c in candidates if c.qualities.get("fundamental") != "missing")
    return filled, max(0, len(candidates) - filled)

WatchlistFilter = Literal["early", "ignition", "running"]
StageFilter = Literal[
    "dormant",
    "fundamental_inflection",
    "early_accumulation",
    "catalyst",
    "ignition",
    "discovery",
    "momentum",
    "extended",
]


def _scores_to_schema(scores) -> RunnerScoresSchema:
    return RunnerScoresSchema(
        fundamental=scores.fundamental,
        catalyst=scores.catalyst,
        structure=scores.structure,
        asymmetry=scores.asymmetry,
        discovery_gap=scores.discovery_gap,
        theme_bottleneck=scores.theme_bottleneck,
        institutional_accum=scores.institutional_accum,
        short_squeeze_potential=scores.short_squeeze_potential,
        runner_score=scores.runner_score,
        risk_score=scores.risk_score,
        penalties=scores.penalties,
    )


def _to_schema(candidate: RunnerCandidate) -> RunnerCandidateSchema:
    return RunnerCandidateSchema(
        id=candidate.id,
        symbol=candidate.symbol,
        instrument_type=candidate.instrument_type,
        stage=candidate.stage,
        signal_type=candidate.signal_type,
        watchlist=candidate.watchlist,
        alert_gate=candidate.alert_gate,
        scores=_scores_to_schema(candidate.scores),
        factors=list(candidate.factors),
        conflicts=list(candidate.conflicts),
        risk_flags=list(candidate.risk_flags),
        confidence=candidate.confidence,
        data_quality=candidate.data_quality,
        as_of=candidate.as_of,
        phase=candidate.phase,
        qualities=dict(candidate.qualities),
        ret_20d_pct=candidate.tape.ret_20d_pct,
        relative_volume=candidate.tape.relative_volume,
        rs_benchmark=candidate.tape.rs_benchmark,
        rs_pct=candidate.tape.rs_pct,
    )


def _crypto_to_schema(candidate: CryptoRadarCandidate) -> CryptoRadarCandidateSchema:
    return CryptoRadarCandidateSchema(
        id=candidate.id,
        symbol=candidate.symbol,
        bucket=candidate.bucket,
        score=candidate.score,
        factors=list(candidate.factors),
        conflicts=list(candidate.conflicts),
        mom_12h_pct=candidate.mom_12h_pct,
        mom_20d_pct=candidate.mom_20d_pct,
        funding_bps=candidate.funding_bps,
        oi_change_pct=candidate.oi_change_pct,
        funding_source=candidate.funding_source,
        mark_price=candidate.mark_price,
        basis_pct=getattr(candidate, "basis_pct", None),
        as_of=candidate.as_of,
    )


@router.get("/crypto", response_model=CryptoRadarFeedResponse)
async def list_crypto_radar() -> CryptoRadarFeedResponse:
    """Crypto movers track — Watch / Crowded / Running on the V2 universe."""
    try:
        buckets = await asyncio.to_thread(crypto_radar_lists)
    except Exception:
        logger.exception("Crypto radar scan failed")
        buckets = {"watch": [], "crowded": [], "running": [], "all": []}

    all_cands: list[CryptoRadarCandidate] = buckets.get("all", [])
    funding_filled = sum(1 for c in all_cands if c.funding_bps is not None)
    coeffs = get_crypto_learn_coefficients()
    try:
        expectancy = perp_momentum_expectancy(get_learning_engine())
    except Exception:
        logger.debug("perp_momentum expectancy unavailable", exc_info=True)
        expectancy = {"n": 0, "win_rate": None}
    return CryptoRadarFeedResponse(
        candidates=[_crypto_to_schema(c) for c in all_cands],
        watch=[_crypto_to_schema(c) for c in buckets["watch"]],
        crowded=[_crypto_to_schema(c) for c in buckets["crowded"]],
        running=[_crypto_to_schema(c) for c in buckets["running"]],
        scanned_at=datetime.now(UTC),
        symbols_scanned=len(CRYPTO_RADAR_UNIVERSE),
        funding_filled=funding_filled,
        universe=list(CRYPTO_RADAR_UNIVERSE),
        coefficients_preset=coeffs.preset,
        perp_momentum_n=int(expectancy.get("n") or 0),
        perp_momentum_win_rate=(
            float(expectancy["win_rate"]) if expectancy.get("win_rate") is not None else None
        ),
    )


@router.get("", response_model=RunnerFeedResponse)
async def list_runners(
    watchlist: WatchlistFilter | None = Query(
        None, description="Filter EARLY / IGNITION / RUNNING"
    ),
    min_runner_score: float = Query(0.0, ge=0.0, le=100.0),
    stage: StageFilter | None = Query(None, description="Filter by runner stage"),
    scanner: RunnerScanner = Depends(get_runner_scanner),
) -> RunnerFeedResponse:
    """Return ranked Surface 4 runner candidates for the seed universe."""
    try:
        candidates = await asyncio.to_thread(
            scanner.scan,
            None,
            watchlist=watchlist,
            min_runner_score=min_runner_score,
            stage=stage,
        )
    except Exception:
        logger.exception("Runner feed scan failed")
        candidates = []

    filled, missing = _fundamentals_counts(candidates)
    return RunnerFeedResponse(
        candidates=[_to_schema(c) for c in candidates],
        scanned_at=datetime.now(UTC),
        symbols_scanned=len(scanner.universe),
        fundamentals_filled=filled,
        fundamentals_missing=missing,
        watchlist=watchlist,
        min_runner_score=min_runner_score,
        stage=stage,
    )


@router.get("/lists", response_model=RunnerListsResponse)
async def list_runner_watchlists(
    scanner: RunnerScanner = Depends(get_runner_scanner),
) -> RunnerListsResponse:
    """Return EARLY / IGNITION / RUNNING buckets."""
    try:
        buckets = await asyncio.to_thread(scanner.lists)
        all_scanned = await asyncio.to_thread(scanner.scan)
    except Exception:
        logger.exception("Runner watchlist scan failed")
        buckets = {"early": [], "ignition": [], "running": []}
        all_scanned = []

    filled, missing = _fundamentals_counts(all_scanned)
    return RunnerListsResponse(
        early=[_to_schema(c) for c in buckets["early"]],
        ignition=[_to_schema(c) for c in buckets["ignition"]],
        running=[_to_schema(c) for c in buckets["running"]],
        scanned_at=datetime.now(UTC),
        symbols_scanned=len(scanner.universe),
        fundamentals_filled=filled,
        fundamentals_missing=missing,
    )


@router.get("/meta/config", response_model=RunnerConfigMetaResponse)
async def get_runner_config_meta() -> RunnerConfigMetaResponse:
    """Public runner thresholds and seed universe (no secrets)."""
    cfg = default_runner_config()
    return RunnerConfigMetaResponse(
        seed_universe=list(cfg.seed_universe),
        alert_high_runner_min=cfg.alerts.high_runner_min,
        alert_standard_runner_min=cfg.alerts.standard_runner_min,
        alert_early_fundamental_min=cfg.alerts.early_fundamental_min,
        alert_early_discovery_gap_min=cfg.alerts.early_discovery_gap_min,
        phase=RUNNER_PHASE,
    )


def _snapshot_schema(point) -> RunnerBacktestSnapshotSchema:
    return RunnerBacktestSnapshotSchema(
        offset_days=point.offset_days,
        as_of=point.as_of,
        last_close=point.last_close,
        stage=point.stage,
        watchlist=point.watchlist,
        runner_score=point.scores.runner_score,
        structure=point.scores.structure,
        fundamentals_available=point.fundamentals_available,
    )


def _case_schema(case) -> RunnerBacktestCaseSchema:
    return RunnerBacktestCaseSchema(
        symbol=case.symbol,
        bars=case.bars,
        error=case.error,
        trough_date=case.trough_date,
        hit_2x=case.hit_2x,
        hit_5x=case.hit_5x,
        hit_10x=case.hit_10x,
        date_2x=case.date_2x,
        date_5x=case.date_5x,
        date_10x=case.date_10x,
        days_to_2x=case.days_to_2x,
        days_to_5x=case.days_to_5x,
        days_to_10x=case.days_to_10x,
        first_early=case.first_early,
        first_ignition=case.first_ignition,
        first_running=case.first_running,
        lead_days_to_2x=case.lead_days_to_2x,
        late_for_2x=case.late_for_2x,
        max_dd_after_early_pct=case.max_dd_after_early_pct,
        snapshots=[_snapshot_schema(s) for s in case.snapshots],
    )


@router.get("/backtest", response_model=RunnerBacktestResponse)
async def get_runner_backtest() -> RunnerBacktestResponse:
    """Lead-time study on pattern names.

    Truncates daily bars at each as-of. Dated 8-K filing dates and lagged
    Yahoo quarterlies may fill fund/catalyst. Live Yahoo info is not scored
    back through history (that would look ahead).
    """
    try:
        study = await asyncio.to_thread(cached_live_study)
    except Exception:
        logger.exception("Runner lead-time study failed")
        raise HTTPException(
            status_code=502,
            detail="Runner lead-time study failed",
        ) from None

    return RunnerBacktestResponse(
        phase=study.phase,
        mode=study.mode,
        generated_at=study.generated_at,
        look_ahead=study.look_ahead,
        symbols=list(STUDY_SYMBOLS),
        cases=[_case_schema(c) for c in study.cases],
        metrics=RunnerBacktestMetricsSchema(**study.metrics.__dict__),
    )


def _tune_metrics(metrics) -> RunnerBacktestMetricsSchema:
    return RunnerBacktestMetricsSchema(**metrics.__dict__)


def _tune_row_schema(row) -> RunnerTuneGridRowSchema:
    return RunnerTuneGridRowSchema(
        structure_accumulation=row.structure_accumulation,
        is_baseline=row.is_baseline,
        train_score=row.train_score,
        holdout_score=row.holdout_score,
        train=_tune_metrics(row.train_metrics),
        holdout=_tune_metrics(row.holdout_metrics),
    )


@router.get("/tune", response_model=RunnerTuneResponse)
async def get_runner_tune() -> RunnerTuneResponse:
    """Phase 6 v0: OOS structure-accumulation grid vs structure-only baseline.

    Famous pattern-study names are holdout and never pick the threshold.
    Does not change live Radar defaults.
    """
    try:
        report = await asyncio.to_thread(cached_live_tune)
    except Exception:
        logger.exception("Runner structure-threshold tune failed")
        raise HTTPException(
            status_code=502,
            detail="Runner structure-threshold tune failed",
        ) from None

    def _row_at(threshold: float):
        return next(
            r for r in report.rows if r.structure_accumulation == threshold
        )

    baseline = _row_at(report.baseline_structure_accumulation)
    recommended = _row_at(report.recommended_structure_accumulation)
    return RunnerTuneResponse(
        phase=report.phase,
        mode=report.mode,
        generated_at=report.generated_at,
        note=report.note,
        train_symbols=list(report.train_symbols),
        holdout_symbols=list(report.holdout_symbols),
        grid=list(report.grid),
        baseline_structure_accumulation=report.baseline_structure_accumulation,
        train_winner_structure_accumulation=report.train_winner_structure_accumulation,
        recommended_structure_accumulation=report.recommended_structure_accumulation,
        applied_to_live=report.applied_to_live,
        holdout_accepts_tuned=report.holdout_accepts_tuned,
        baseline_train=_tune_metrics(baseline.train_metrics),
        baseline_holdout=_tune_metrics(baseline.holdout_metrics),
        recommended_train=_tune_metrics(recommended.train_metrics),
        recommended_holdout=_tune_metrics(recommended.holdout_metrics),
        rows=[_tune_row_schema(r) for r in report.rows],
    )


@router.get("/{symbol}", response_model=RunnerDetailResponse)
async def get_runner_detail(
    symbol: str,
    scanner: RunnerScanner = Depends(get_runner_scanner),
) -> RunnerDetailResponse:
    """Return full runner score breakdown for one symbol.

    Accepts any symbol (seed universe is not a hard gate) so Phase 2+ can
    evaluate ad-hoc tickers without polluting Surface 1 tracked assets.
    """
    normalized = symbol.upper().strip()
    if not normalized or len(normalized) > 12:
        raise HTTPException(status_code=400, detail="Invalid symbol")

    try:
        candidate = await asyncio.to_thread(scanner.evaluate, normalized)
    except Exception:
        logger.exception("Runner evaluate failed for %s", normalized)
        raise HTTPException(
            status_code=502,
            detail=f"Runner evaluate failed for {normalized}",
        ) from None

    return RunnerDetailResponse(
        candidate=_to_schema(candidate),
        scanned_at=datetime.now(UTC),
    )
