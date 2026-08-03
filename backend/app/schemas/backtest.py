"""Backtesting API schemas."""

from pydantic import BaseModel, Field


class BacktestResultSchema(BaseModel):
    """Walk-forward backtest summary."""

    symbol: str
    timeframe: str
    hold_bars: int
    signal_threshold: float
    total_signals: int
    wins: int
    losses: int
    win_rate: float = Field(..., description="Win rate percentage")
    avg_return_pct: float
    best_return_pct: float
    worst_return_pct: float
    description: str
