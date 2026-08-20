"""Surface 5 — Market Expansion Radar API."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.service_dependencies import get_expansion_scanner, get_market_data_service
from app.engines.expansion_engine.config import BENCHMARK_UNIVERSE, EXPANSION_PHASE, EXPANSION_UNIVERSE
from app.engines.expansion_engine.replay import replay_universe
from app.engines.expansion_engine.scanner import ExpansionScanner
from app.engines.expansion_engine.types import ExpansionCandidate, ExpansionState
from app.schemas.expansion import (
    CompressionSchema,
    ExpansionCandidateSchema,
    ExpansionFeedResponse,
    ExpansionReplayResponse,
    ReplayEventSchema,
    ScoreContributorSchema,
    SqueezeFuelLevelSchema,
    SqueezeFuelSchema,
    TriggerSchema,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _compression_schema(c: ExpansionCandidate) -> CompressionSchema:
    comp = c.compression
    return CompressionSchema(
        score=comp.score,
        atr_percentile=comp.atr_percentile,
        bb_width_percentile=comp.bb_width_percentile,
        range_compression_pct=comp.range_compression_pct,
        volume_compression_pct=comp.volume_compression_pct,
        factors=list(comp.factors),
    )


def _squeeze_schema(c: ExpansionCandidate) -> SqueezeFuelSchema:
    sq = c.squeeze
    return SqueezeFuelSchema(
        score=sq.score,
        direction=sq.direction,
        levels=[
            SqueezeFuelLevelSchema(pct_move=level.pct_move, label=level.label)
            for level in sq.levels
        ],
        factors=list(sq.factors),
        conflicts=list(sq.conflicts),
    )


def _trigger_schema(c: ExpansionCandidate) -> TriggerSchema:
    tr = c.trigger
    return TriggerSchema(
        active=tr.active,
        direction=tr.direction,
        volume_ratio=tr.volume_ratio,
        breakout_level=tr.breakout_level,
        factors=list(tr.factors),
    )


def _to_schema(candidate: ExpansionCandidate) -> ExpansionCandidateSchema:
    return ExpansionCandidateSchema(
        id=candidate.id,
        symbol=candidate.symbol,
        state=candidate.state.value,
        direction_bias=candidate.direction_bias,
        up_score=candidate.up_score,
        down_score=candidate.down_score,
        net_score=candidate.net_score,
        confidence=candidate.confidence,
        setup_level=candidate.setup_level,
        trigger_active=candidate.trigger_active,
        horizon=candidate.horizon,
        invalidation=candidate.invalidation,
        key_trigger=candidate.key_trigger,
        compression=_compression_schema(candidate),
        squeeze=_squeeze_schema(candidate),
        trigger=_trigger_schema(candidate),
        contributors=[
            ScoreContributorSchema(label=x.label, points=x.points, detail=x.detail)
            for x in candidate.contributors
        ],
        conflicts=list(candidate.conflicts),
        factors=list(candidate.factors),
        price=candidate.price,
        funding_bps=candidate.funding_bps,
        oi_change_pct=candidate.oi_change_pct,
        mom_12h_pct=candidate.mom_12h_pct,
        as_of=candidate.as_of or datetime.now(UTC),
    )


@router.get("", response_model=ExpansionFeedResponse)
def get_expansion_feed(
    scanner: ExpansionScanner = Depends(get_expansion_scanner),
    use_cache: bool = Query(True, description="Use 60s scan cache"),
) -> ExpansionFeedResponse:
    """Expansion radar for perp v2 universe (16 symbols)."""
    candidates = scanner.scan(use_cache=use_cache)
    schemas = [_to_schema(c) for c in candidates]
    primed = [s for s in schemas if s.state == ExpansionState.PRIMED.value]
    triggering = [s for s in schemas if s.state == ExpansionState.TRIGGERING.value]
    expanding = [s for s in schemas if s.state == ExpansionState.EXPANDING.value]
    return ExpansionFeedResponse(
        candidates=schemas,
        primed=primed,
        triggering=triggering,
        expanding=expanding,
        scanned_at=datetime.now(UTC),
        symbols_scanned=len(candidates),
        universe=list(scanner._config.universe or EXPANSION_UNIVERSE),
        phase=EXPANSION_PHASE,
    )


@router.get("/replay", response_model=ExpansionReplayResponse)
def get_expansion_replay(
    market=Depends(get_market_data_service),
) -> ExpansionReplayResponse:
    """Lead-time replay vs paper v2 momentum gate on benchmark symbols."""
    events = replay_universe(market, BENCHMARK_UNIVERSE)
    return ExpansionReplayResponse(
        events=[
            ReplayEventSchema(
                symbol=e.symbol,
                max_move_pct=e.max_move_pct,
                primed_hours_before_move=e.primed_hours_before_move,
                v2_hours_after_move_start=e.v2_hours_after_move_start,
                primed_before_v2=e.primed_before_v2,
            )
            for e in events
        ],
        benchmark_symbols=list(BENCHMARK_UNIVERSE),
        scanned_at=datetime.now(UTC),
    )


@router.get("/{symbol}", response_model=ExpansionCandidateSchema)
def get_expansion_symbol(
    symbol: str,
    scanner: ExpansionScanner = Depends(get_expansion_scanner),
) -> ExpansionCandidateSchema:
    """Single-symbol expansion breakdown."""
    normalized = symbol.upper().strip()
    candidate = scanner.scan_symbol(normalized)
    if candidate is None:
        raise HTTPException(status_code=404, detail=f"No expansion data for {normalized}")
    return _to_schema(candidate)
