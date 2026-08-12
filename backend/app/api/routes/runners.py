"""Surface 4 Runner Detection API endpoints."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.service_dependencies import get_runner_scanner
from app.engines.runner_engine.config import default_runner_config
from app.engines.runner_engine.scanner import RunnerScanner
from app.engines.runner_engine.types import RunnerCandidate
from app.schemas.runners import (
    RunnerCandidateSchema,
    RunnerConfigMetaResponse,
    RunnerDetailResponse,
    RunnerFeedResponse,
    RunnerListsResponse,
    RunnerScoresSchema,
)

logger = logging.getLogger(__name__)

router = APIRouter()

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
        scores=_scores_to_schema(candidate.scores),
        factors=list(candidate.factors),
        conflicts=list(candidate.conflicts),
        risk_flags=list(candidate.risk_flags),
        confidence=candidate.confidence,
        data_quality=candidate.data_quality,
        as_of=candidate.as_of,
        phase=candidate.phase,
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

    return RunnerFeedResponse(
        candidates=[_to_schema(c) for c in candidates],
        scanned_at=datetime.now(UTC),
        symbols_scanned=len(scanner.universe),
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
    except Exception:
        logger.exception("Runner watchlist scan failed")
        buckets = {"early": [], "ignition": [], "running": []}

    return RunnerListsResponse(
        early=[_to_schema(c) for c in buckets["early"]],
        ignition=[_to_schema(c) for c in buckets["ignition"]],
        running=[_to_schema(c) for c in buckets["running"]],
        scanned_at=datetime.now(UTC),
        symbols_scanned=len(scanner.universe),
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
        phase="1_stub",
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
