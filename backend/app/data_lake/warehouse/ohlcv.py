"""OHLCV warehouse read/write (Phase B)."""

from __future__ import annotations

from typing import Any


async def get_bars(symbol: str, timeframe: str, limit: int = 200) -> list[dict[str, Any]]:
    """Fetch bars from warehouse; falls back to live API in MVP."""
    raise NotImplementedError("warehouse reads use live OHLCV until Phase B")
