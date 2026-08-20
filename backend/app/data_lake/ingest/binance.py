"""Binance OHLCV backfill stub (Phase B)."""

from __future__ import annotations


async def backfill_ohlcv(symbol: str, timeframe: str, days: int = 90) -> int:
    """Return number of bars ingested. Not implemented in MVP."""
    raise NotImplementedError("data_lake backfill scheduled for Phase B")
