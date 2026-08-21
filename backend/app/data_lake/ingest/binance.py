"""Ingest live OHLCV into the warehouse (Kraken/Binance via MarketDataService)."""

from __future__ import annotations

import logging

from app.data_lake.warehouse.ohlcv import persist_ohlcv_frame

logger = logging.getLogger(__name__)


def ingest_ohlcv(symbol: str, timeframe: str, days: int = 90) -> int:
    """Fetch live bars and persist. ``days`` sizes the limit (~24 bars/day on 1h)."""
    from app.core.service_dependencies import get_market_data_service

    limit = max(50, min(1000, int(days * 24) if timeframe == "1h" else days * 8))
    market = get_market_data_service()
    df = market.safe_get_ohlcv(symbol, timeframe, limit=limit)
    if df is None or df.empty:
        return 0
    return persist_ohlcv_frame(df, symbol=symbol, timeframe=timeframe, source="ingest")


async def backfill_ohlcv(symbol: str, timeframe: str, days: int = 90) -> int:
    """Async wrapper used by older call sites."""
    return ingest_ohlcv(symbol, timeframe, days=days)
