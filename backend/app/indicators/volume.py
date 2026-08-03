"""Volume analysis indicators."""

import pandas as pd


def calculate_volume_sma(volume: pd.Series, period: int = 20) -> pd.Series:
    """Calculate simple moving average of volume.

    Args:
        volume: Volume series.
        period: Lookback period.

    Returns:
        Series of volume SMA values.
    """
    return volume.rolling(window=period, min_periods=period).mean()


def calculate_volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """Calculate current volume relative to its moving average.

    Args:
        volume: Volume series.
        period: Lookback period for the average.

    Returns:
        Series where 1.0 means average volume, >1.0 means expanded volume.
    """
    sma = calculate_volume_sma(volume, period)
    return (volume / sma.replace(0, pd.NA)).fillna(1.0)


def calculate_buying_pressure(
    open_: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = 20,
) -> pd.Series:
    """Estimate buying pressure from bullish candle volume share.

    Args:
        open_: Open price series.
        close: Close price series.
        volume: Volume series.
        period: Rolling window for averaging.

    Returns:
        Series of buying pressure scores from 0–100.
    """
    bullish_volume = volume.where(close >= open_, 0.0)
    total_volume = volume.rolling(window=period, min_periods=period).sum()
    bullish_sum = bullish_volume.rolling(window=period, min_periods=period).sum()
    ratio = (bullish_sum / total_volume.replace(0, pd.NA)).fillna(0.5)
    return (ratio * 100).clip(0, 100)
