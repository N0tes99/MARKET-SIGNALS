"""Layer 3 equity-options setup endpoints."""

import asyncio
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.tracked import is_tracked
from app.core.service_dependencies import get_equity_options_scanner
from app.engines.opportunity_engine.equity_options.scanner import (
    EQUITY_UNIVERSE,
    EquityOptionsScanner,
)
from app.engines.opportunity_engine.equity_options.types import EquityOptionsIdea
from app.schemas.equity_setups import (
    AssetEquitySetupsResponse,
    EquityOptionsIdeaSchema,
    ExecutionPlanSchema,
    GlobalEquitySetupsResponse,
    OptionCandidateSchema,
    ProfitZoneSchema,
    StagedEntrySchema,
)

logger = logging.getLogger(__name__)

router = APIRouter()
feed_router = APIRouter()


def _option_to_schema(opt) -> OptionCandidateSchema:
    return OptionCandidateSchema(
        underlying=opt.underlying,
        expiry=opt.expiry,
        strike=opt.strike,
        right=opt.right,
        bid=opt.bid,
        ask=opt.ask,
        mid=opt.mid,
        volume=opt.volume,
        open_interest=opt.open_interest,
        iv=opt.iv,
        otm_pct=opt.otm_pct,
        dte=opt.dte,
        convexity_score=opt.convexity_score,
        liquidity_score=opt.liquidity_score,
        theta_score=opt.theta_score,
        iv_value_score=opt.iv_value_score,
        overall_score=opt.overall_score,
        rationale=opt.rationale,
    )


def _plan_to_schema(plan) -> ExecutionPlanSchema:
    return ExecutionPlanSchema(
        setup_name=plan.setup_name,
        direction=plan.direction,
        max_risk_usd=plan.max_risk_usd,
        entries=[
            StagedEntrySchema(
                step=e.step,
                label=e.label,
                size_pct=e.size_pct,
                condition=e.condition,
                price_trigger=e.price_trigger,
            )
            for e in plan.entries
        ],
        invalidation=list(plan.invalidation),
        profit_zones=[
            ProfitZoneSchema(
                option_gain_pct=z.option_gain_pct,
                take_pct=z.take_pct,
                label=z.label,
            )
            for z in plan.profit_zones
        ],
        runner_pct=plan.runner_pct,
        runner_rule=getattr(plan, "runner_rule", "") or "",
        notes=plan.notes,
    )


def _to_schema(idea: EquityOptionsIdea) -> EquityOptionsIdeaSchema:
    return EquityOptionsIdeaSchema(
        id=idea.id,
        symbol=idea.symbol,
        instrument_type=idea.instrument_type,
        setup_type=idea.setup_type,
        direction_bias=idea.direction_bias,
        confidence=idea.confidence,
        opportunity_score=idea.opportunity_score,
        factors=idea.factors,
        conflicts=idea.conflicts,
        trade_state_hint=idea.trade_state_hint,
        momentum_score=idea.momentum_score,
        catalyst_score=idea.catalyst_score,
        liquidity_score=idea.liquidity_score,
        option_candidates=[_option_to_schema(c) for c in idea.option_candidates],
        selected_option=_option_to_schema(idea.selected_option)
        if idea.selected_option
        else None,
        execution_plan=_plan_to_schema(idea.execution_plan) if idea.execution_plan else None,
        as_of=idea.as_of,
        data_quality=idea.data_quality,
    )


@feed_router.get("", response_model=GlobalEquitySetupsResponse)
async def list_equity_setups_feed(
    watch_only: bool = Query(False, description="If true, only WATCH hints"),
    min_confidence: float = Query(0.0, ge=0.0, le=100.0),
    scanner: EquityOptionsScanner = Depends(get_equity_options_scanner),
) -> GlobalEquitySetupsResponse:
    """Return Layer 3 equity-options setup ideas across tracked stocks/ETFs."""
    try:
        ideas = await asyncio.to_thread(
            scanner.scan_feed,
            EQUITY_UNIVERSE,
            watch_only=watch_only,
            min_confidence=min_confidence,
        )
    except Exception:
        logger.exception("Layer 3 equity setup feed failed")
        ideas = []

    return GlobalEquitySetupsResponse(
        setups=[_to_schema(i) for i in ideas],
        scanned_at=datetime.now(UTC),
        symbols_scanned=len(EQUITY_UNIVERSE),
        watch_only=watch_only,
        min_confidence=min_confidence,
    )


@router.get("/{symbol}/equity-setups", response_model=AssetEquitySetupsResponse)
async def get_asset_equity_setups(
    symbol: str,
    scanner: EquityOptionsScanner = Depends(get_equity_options_scanner),
) -> AssetEquitySetupsResponse:
    """Return Layer 3 equity-options ideas for one asset."""
    normalized = symbol.upper()
    if not is_tracked(normalized):
        raise HTTPException(status_code=404, detail=f"Asset '{normalized}' is not tracked")

    try:
        ideas = await asyncio.to_thread(scanner.scan, normalized)
    except Exception:
        logger.exception("Layer 3 equity setup scan failed for %s", normalized)
        ideas = []

    return AssetEquitySetupsResponse(
        symbol=normalized,
        setups=[_to_schema(i) for i in ideas],
        scanned_at=datetime.now(UTC),
    )
