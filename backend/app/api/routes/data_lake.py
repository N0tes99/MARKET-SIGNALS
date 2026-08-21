"""OHLCV warehouse API."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.data_lake.warehouse.ohlcv import backend_name, get_bars

router = APIRouter()


@router.get("/ohlcv/{symbol}")
def get_warehouse_ohlcv(
    symbol: str,
    timeframe: str = Query("1h"),
    limit: int = Query(200, ge=10, le=1000),
) -> dict:
    """Persisted candles when the warehouse has them; empty list otherwise."""
    bars = get_bars(symbol, timeframe, limit=limit)
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "backend": backend_name(),
        "count": len(bars),
        "bars": [
            {
                "ts": bar.ts.isoformat(),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in bars
        ],
    }
