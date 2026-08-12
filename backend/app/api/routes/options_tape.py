"""Aggressive options tape endpoints."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query

from app.api.routes.equity_setups import _option_to_schema, _plan_to_schema
from app.core.service_dependencies import get_options_tape_scanner
from app.engines.options_tape.engine import OptionsTapeScanner
from app.engines.options_tape.types import TapeHunt
from app.schemas.options_tape import TapeBoardResponse, TapeHuntSchema

logger = logging.getLogger(__name__)

router = APIRouter()


def _hunt_to_schema(hunt: TapeHunt) -> TapeHuntSchema:
    return TapeHuntSchema(
        id=hunt.id,
        symbol=hunt.symbol,
        direction=hunt.direction,
        heat=hunt.heat,
        hunt_score=hunt.hunt_score,
        relative_volume=hunt.relative_volume,
        range_expansion=hunt.range_expansion,
        ret_5d_pct=hunt.ret_5d_pct,
        ret_20d_pct=hunt.ret_20d_pct,
        put_call_vol=hunt.put_call_vol,
        option_volume=hunt.option_volume,
        unusual_vol_oi=hunt.unusual_vol_oi,
        factors=list(hunt.factors),
        conflicts=list(hunt.conflicts),
        selected_option=_option_to_schema(hunt.selected_option)
        if hunt.selected_option
        else None,
        option_candidates=[_option_to_schema(c) for c in hunt.option_candidates],
        execution_plan=_plan_to_schema(hunt.execution_plan) if hunt.execution_plan else None,
        as_of=hunt.as_of,
    )


@router.get("", response_model=TapeBoardResponse)
async def get_options_tape(
    per_side: int = Query(5, ge=1, le=8),
    min_rel_vol: float = Query(1.15, ge=0.5, le=4.0),
    add: str = Query("", description="Comma-separated extra US tickers"),
    scanner: OptionsTapeScanner = Depends(get_options_tape_scanner),
) -> TapeBoardResponse:
    """Volume-first long/short options board. Untracked tickers are allowed."""
    extra = [part.strip() for part in add.split(",") if part.strip()]
    try:
        board = await asyncio.to_thread(
            scanner.scan_board,
            extra_symbols=extra or None,
            per_side=per_side,
            min_rel_vol=min_rel_vol,
        )
    except Exception:
        logger.exception("Options tape scan failed")
        return TapeBoardResponse(
            longs=[],
            shorts=[],
            symbols_scanned=0,
            symbols_optioned=0,
            per_side=per_side,
            scanned_at=datetime.now(UTC),
            note="tape unavailable",
        )

    return TapeBoardResponse(
        longs=[_hunt_to_schema(h) for h in board.longs],
        shorts=[_hunt_to_schema(h) for h in board.shorts],
        symbols_scanned=board.symbols_scanned,
        symbols_optioned=board.symbols_optioned,
        per_side=board.per_side,
        scanned_at=board.scanned_at,
        note=board.note,
    )
