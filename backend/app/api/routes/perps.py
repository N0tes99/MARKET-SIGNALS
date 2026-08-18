"""Crypto perps activity board API."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from app.core.service_dependencies import get_setup_scanner
from app.engines.opportunity_engine.scanner import SetupScanner
from app.engines.paper_agent.perps_board import build_perps_board
from app.schemas.perps import PerpsBoardSchema

router = APIRouter()


@router.get("/board", response_model=PerpsBoardSchema)
async def get_perps_board(
    scanner: SetupScanner = Depends(get_setup_scanner),
) -> PerpsBoardSchema:
    """Funding board (Bybit→OKX) + public liquidations + Layer-2 ideas."""
    return await asyncio.to_thread(build_perps_board, setup_scanner=scanner)
