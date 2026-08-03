"""Exponential Moving Average indicator."""

import pandas as pd


def calculate_ema(series: pd.Series, period: int = 20) -> pd.Series:
    """Calculate Exponential Moving Average for a price series.

    Args:
        series: Price series (typically close prices).
        period: EMA lookback period.

    Returns:
        Series of EMA values aligned with the input index.
    """
    return series.ewm(span=period, adjust=False).mean()
