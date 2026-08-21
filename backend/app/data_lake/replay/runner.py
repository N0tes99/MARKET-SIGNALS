"""Replay runner over warehouse bars, falling back to live OHLCV."""

from __future__ import annotations

from datetime import datetime

from app.data_lake.warehouse.ohlcv import bars_to_frame, get_bars
from app.engines.expansion_engine.replay import ReplayEvent
from app.engines.expansion_engine.replay import replay_symbol as expansion_replay_symbol


def replay_symbol_from_warehouse(
    symbol: str,
    start_iso: str | None = None,
    end_iso: str | None = None,
) -> ReplayEvent | None:
    """Replay expansion lead-time using warehouse 1h bars when present."""
    bars = get_bars(symbol, "1h", limit=500)
    if start_iso:
        start = datetime.fromisoformat(start_iso)
        bars = [b for b in bars if b.ts >= start]
    if end_iso:
        end = datetime.fromisoformat(end_iso)
        bars = [b for b in bars if b.ts <= end]
    df = bars_to_frame(bars)
    if df.empty or len(df) < 40:
        return None
    return expansion_replay_symbol(df, symbol)


async def replay_symbol(symbol: str, start_iso: str, end_iso: str) -> dict:
    event = replay_symbol_from_warehouse(symbol, start_iso, end_iso)
    if event is None:
        return {"symbol": symbol, "found": False}
    return {
        "symbol": event.symbol,
        "found": True,
        "max_move_pct": event.max_move_pct,
        "primed_hours_before_move": event.primed_hours_before_move,
        "v2_hours_after_move_start": event.v2_hours_after_move_start,
        "primed_before_v2": event.primed_before_v2,
    }
