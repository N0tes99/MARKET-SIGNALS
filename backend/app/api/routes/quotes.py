"""Price quote endpoints."""

import asyncio

from fastapi import APIRouter, Depends

from app.core.service_dependencies import get_market_data_service
from app.market_data.service import MarketDataService
from app.schemas.quotes import AssetQuote
from app.services.quote_service import build_quote, load_all_quotes

router = APIRouter()


@router.get("", response_model=list[AssetQuote])
async def list_quotes(
    market_data: MarketDataService = Depends(get_market_data_service),
) -> list[AssetQuote]:
    """Return cached price feeds for all tracked assets."""
    return await asyncio.to_thread(load_all_quotes, market_data)


@router.get("/{symbol}", response_model=AssetQuote)
async def get_quote(
    symbol: str,
    market_data: MarketDataService = Depends(get_market_data_service),
) -> AssetQuote:
    """Return a single asset quote."""
    return await asyncio.to_thread(build_quote, market_data, symbol.upper())
