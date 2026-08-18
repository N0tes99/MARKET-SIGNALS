"""CME / traditional futures board API."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter

from app.engines.runner_engine.cme_futures import build_cme_futures_board
from app.schemas.cme_futures import CmeFuturesBoardSchema

router = APIRouter()


@router.get("/board", response_model=CmeFuturesBoardSchema)
async def get_futures_board() -> CmeFuturesBoardSchema:
    """Yahoo continuous front-month scan (ES, NQ, CL, GC, …). Not a live CME feed."""
    return await asyncio.to_thread(build_cme_futures_board)
