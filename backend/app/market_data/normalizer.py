"""OHLCV data normalization utilities."""

import pandas as pd

from app.market_data.types import Candle

STANDARD_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def candles_to_dataframe(candles: list[Candle]) -> pd.DataFrame:
    """Convert a list of candles to a normalized OHLCV DataFrame."""
    if not candles:
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    return pd.DataFrame(
        [
            {
                "timestamp": candle.timestamp,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            }
            for candle in candles
        ]
    )


def validate_ohlcv(df: pd.DataFrame, min_rows: int = 50) -> pd.DataFrame:
    """Validate that OHLCV data has required columns and minimum rows.

    Args:
        df: OHLCV DataFrame to validate.
        min_rows: Minimum required row count.

    Returns:
        Validated DataFrame.

    Raises:
        ValueError: If data is invalid or insufficient.
    """
    missing = set(STANDARD_COLUMNS) - set(df.columns)
    if missing:
        msg = f"OHLCV data missing columns: {missing}"
        raise ValueError(msg)

    if len(df) < min_rows:
        msg = f"Insufficient OHLCV data: need {min_rows} rows, got {len(df)}"
        raise ValueError(msg)

    return df.copy()
