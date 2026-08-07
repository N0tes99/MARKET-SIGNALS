"""Asset setup ideas (opportunity scanner) endpoints."""

import asyncio
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from app.api.tracked import is_tracked
from app.core.service_dependencies import get_setup_scanner
from app.engines.opportunity_engine.scanner import SetupScanner
from app.schemas.setups import AssetSetupsResponse, OpportunityIdeaSchema

logger = logging.getLogger(__name__)

router = APIRouter()


def _to_schema(idea) -> OpportunityIdeaSchema:
    return OpportunityIdeaSchema(
        id=idea.id,
        symbol=idea.symbol,
        instrument_type=idea.instrument_type,
        setup_type=idea.setup_type,
        direction_bias=idea.direction_bias,
        confidence=idea.confidence,
        factors=idea.factors,
        conflicts=idea.conflicts,
        trade_state_hint=idea.trade_state_hint,
        as_of=idea.as_of,
        data_quality=idea.data_quality,
    )


@router.get("/{symbol}/setups", response_model=AssetSetupsResponse)
async def get_asset_setups(
    symbol: str,
    scanner: SetupScanner = Depends(get_setup_scanner),
) -> AssetSetupsResponse:
    """Return setup watch ideas for an asset.

    Soft-fails to an empty list when feeds are unavailable.
    Ideas are a second surface — they do not alter asset grading.
    """
    normalized = symbol.upper()
    if not is_tracked(normalized):
        raise HTTPException(status_code=404, detail=f"Asset '{normalized}' is not tracked")

    try:
        ideas = await asyncio.to_thread(scanner.scan, normalized)
    except Exception:
        logger.exception("Setup scan failed for %s", normalized)
        ideas = []

    return AssetSetupsResponse(
        symbol=normalized,
        setups=[_to_schema(i) for i in ideas],
        scanned_at=datetime.now(UTC),
    )
