"""Backtesting metrics."""

from dataclasses import dataclass


@dataclass
class BacktestMetrics:
    """Aggregated backtest performance metrics."""

    symbol: str
    timeframe: str
    hold_bars: int
    signal_threshold: float
    total_signals: int
    wins: int
    losses: int
    win_rate: float
    avg_return_pct: float
    best_return_pct: float
    worst_return_pct: float
    description: str
