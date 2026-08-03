"""Backtesting endpoints."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query

from app.backtesting import BacktestRunner
from app.api.tracked import is_tracked
from app.core.service_dependencies import get_backtest_runner
from app.schemas.backtest import BacktestResultSchema

router = APIRouter()


@router.get("/{symbol}", response_model=BacktestResultSchema)
async def run_asset_backtest(
    symbol: str,
    timeframe: str = Query(default="1h"),
    hold_bars: int = Query(default=24, ge=4, le=72),
    signal_threshold: float = Query(default=55.0, ge=40.0, le=90.0),
    runner: BacktestRunner = Depends(get_backtest_runner),
) -> BacktestResultSchema:
    """Run a walk-forward backtest on historical OHLCV for an asset."""
    normalized = symbol.upper()
    if not is_tracked(normalized):
        raise HTTPException(status_code=404, detail=f"Asset '{normalized}' is not tracked")

    result = await asyncio.to_thread(
        runner.run,
        normalized,
        timeframe,
        hold_bars,
        signal_threshold,
    )

    return BacktestResultSchema(
        symbol=result.symbol,
        timeframe=result.timeframe,
        hold_bars=result.hold_bars,
        signal_threshold=result.signal_threshold,
        total_signals=result.total_signals,
        wins=result.wins,
        losses=result.losses,
        win_rate=result.win_rate,
        avg_return_pct=result.avg_return_pct,
        best_return_pct=result.best_return_pct,
        worst_return_pct=result.worst_return_pct,
        description=result.description,
    )
