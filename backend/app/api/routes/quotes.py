"""Price quote endpoints."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.tracked import is_tracked
from app.core.service_dependencies import get_market_data_service
from app.market_data.service import MarketDataService
from app.market_data.symbols import TIMEFRAME_MAP
from app.schemas.quotes import AssetQuote, CandlePoint, CandleSeries
from app.services.quote_service import build_quote, load_all_quotes
from app.utils.ttl_cache import TTLCache

router = APIRouter()

_CANDLES_CACHE: TTLCache[CandleSeries] = TTLCache(ttl_seconds=30.0)


@router.get("", response_model=list[AssetQuote])
async def list_quotes(
    market_data: MarketDataService = Depends(get_market_data_service),
) -> list[AssetQuote]:
    """Return cached price feeds for all tracked assets."""
    return await asyncio.to_thread(load_all_quotes, market_data)


@router.get("/{symbol}/candles", response_model=CandleSeries)
async def get_candles(
    symbol: str,
    market_data: MarketDataService = Depends(get_market_data_service),
    timeframe: str = Query(default="15m"),
    limit: int = Query(default=96, ge=8, le=200),
) -> CandleSeries:
    """Return OHLCV bars for the asset chart (1m / 5m / 15m / …)."""
    normalized = symbol.upper()
    if not is_tracked(normalized):
        raise HTTPException(status_code=404, detail=f"Symbol '{normalized}' is not tracked")
    if timeframe not in TIMEFRAME_MAP:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe '{timeframe}'")

    cache_key = f"{normalized}:{timeframe}:{limit}"

    def _load() -> CandleSeries:
        # Mini charts: accept short series; do not require engine-grade min_rows.
        try:
            df = market_data.get_ohlcv(
                normalized,
                timeframe=timeframe,
                limit=limit,
                min_rows=8,
            )
        except Exception:
            df = None
        if df is None or df.empty:
            return CandleSeries(symbol=normalized, timeframe=timeframe, candles=[])
        candles: list[CandlePoint] = []
        for _, row in df.tail(limit).iterrows():
            ts = row["timestamp"]
            candles.append(
                CandlePoint(
                    t=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
                    o=float(row["open"]),
                    h=float(row["high"]),
                    low=float(row["low"]),
                    c=float(row["close"]),
                    v=float(row.get("volume", 0) or 0),
                )
            )
        return CandleSeries(symbol=normalized, timeframe=timeframe, candles=candles)

    return await asyncio.to_thread(
        _CANDLES_CACHE.get_stale_while_revalidate,
        cache_key,
        _load,
    )


@router.get("/{symbol}", response_model=AssetQuote)
async def get_quote(
    symbol: str,
    market_data: MarketDataService = Depends(get_market_data_service),
) -> AssetQuote:
    """Return a single asset quote."""
    return await asyncio.to_thread(build_quote, market_data, symbol.upper())
