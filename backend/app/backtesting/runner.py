"""Simple walk-forward backtest using trend-style signals on OHLCV history."""

import pandas as pd

from app.backtesting.metrics import BacktestMetrics
from app.indicators.ema import calculate_ema
from app.indicators.macd import calculate_macd
from app.indicators.rsi import calculate_rsi
from app.market_data.service import MarketDataService
from app.utils.scoring_helpers import (
    clamp_score,
    detect_higher_highs_higher_lows,
    score_from_macd_histogram,
    score_from_rsi,
)


def _confidence_at_index(df: pd.DataFrame, idx: int) -> float:
    """Compute trend-style confidence at a historical bar index."""
    window = df.iloc[: idx + 1]
    close = window["close"]
    if len(close) < 55:
        return 50.0

    price = float(close.iloc[-1])
    ema20 = float(calculate_ema(close, 20).iloc[-1])
    ema50 = float(calculate_ema(close, 50).iloc[-1])
    rsi = float(calculate_rsi(close).iloc[-1])
    _, _, histogram = calculate_macd(close)
    macd_hist = float(histogram.iloc[-1])
    structure_score = detect_higher_highs_higher_lows(window["high"], window["low"])

    trend_score = score_from_rsi(rsi)
    macd_score = score_from_macd_histogram(macd_hist, price)
    confidence = clamp_score((trend_score * 0.5) + (macd_score * 0.3) + (structure_score * 0.2))

    if price < ema20 < ema50 and rsi <= 45:
        confidence = clamp_score(100 - confidence)

    return confidence


class BacktestRunner:
    """Walk-forward backtest on historical OHLCV using confidence threshold signals."""

    def __init__(self, market_data: MarketDataService | None = None) -> None:
        self._market_data = market_data or MarketDataService()

    def run(
        self,
        symbol: str,
        timeframe: str = "1h",
        hold_bars: int = 24,
        signal_threshold: float = 55.0,
    ) -> BacktestMetrics:
        """Simulate entering when confidence exceeds threshold; exit after hold_bars."""
        df = self._market_data.get_ohlcv(symbol, timeframe, limit=200)
        returns: list[float] = []

        min_start = 55
        max_idx = len(df) - hold_bars - 1
        if max_idx <= min_start:
            return BacktestMetrics(
                symbol=symbol.upper(),
                timeframe=timeframe,
                hold_bars=hold_bars,
                signal_threshold=signal_threshold,
                total_signals=0,
                wins=0,
                losses=0,
                win_rate=0.0,
                avg_return_pct=0.0,
                best_return_pct=0.0,
                worst_return_pct=0.0,
                description="Insufficient history for backtest window",
            )

        for idx in range(min_start, max_idx):
            confidence = _confidence_at_index(df, idx)
            if confidence < signal_threshold:
                continue

            entry = float(df["close"].iloc[idx])
            exit_price = float(df["close"].iloc[idx + hold_bars])
            ret_pct = ((exit_price - entry) / entry) * 100
            returns.append(ret_pct)

        if not returns:
            return BacktestMetrics(
                symbol=symbol.upper(),
                timeframe=timeframe,
                hold_bars=hold_bars,
                signal_threshold=signal_threshold,
                total_signals=0,
                wins=0,
                losses=0,
                win_rate=0.0,
                avg_return_pct=0.0,
                best_return_pct=0.0,
                worst_return_pct=0.0,
                description=f"No signals above {signal_threshold:.0f}% confidence in window",
            )

        wins = sum(1 for r in returns if r > 0)
        losses = len(returns) - wins
        win_rate = (wins / len(returns)) * 100

        return BacktestMetrics(
            symbol=symbol.upper(),
            timeframe=timeframe,
            hold_bars=hold_bars,
            signal_threshold=signal_threshold,
            total_signals=len(returns),
            wins=wins,
            losses=losses,
            win_rate=round(win_rate, 1),
            avg_return_pct=round(sum(returns) / len(returns), 2),
            best_return_pct=round(max(returns), 2),
            worst_return_pct=round(min(returns), 2),
            description=(
                f"{len(returns)} signals over {len(df)} bars — "
                f"{win_rate:.0f}% win rate, avg {sum(returns) / len(returns):+.2f}%"
            ),
        )
