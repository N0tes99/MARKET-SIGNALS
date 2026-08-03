"""Shared scoring helpers for analysis engines."""

import pandas as pd


def clamp_score(value: float, low: float = 0.0, high: float = 100.0) -> float:
    """Clamp a numeric value to a score range."""
    return round(min(max(value, low), high), 2)


def score_from_rsi(rsi: float) -> float:
    """Map RSI (0–100) to a directional confidence score."""
    if rsi >= 70:
        return clamp_score(60 + (rsi - 70) * 1.3)
    if rsi <= 30:
        return clamp_score(40 - (30 - rsi) * 1.3)
    return clamp_score(40 + (rsi - 30) * 0.67)


def score_from_macd_histogram(histogram: float, price: float) -> float:
    """Map MACD histogram magnitude to a momentum score."""
    normalized = histogram / price * 10_000
    return clamp_score(50 + normalized * 10)


def detect_higher_highs_higher_lows(high: pd.Series, low: pd.Series, lookback: int = 20) -> float:
    """Score market structure based on swing highs and lows.

    Returns:
        Structure score from 0–100.
    """
    if len(high) < lookback + 2:
        return 50.0

    recent_high = high.iloc[-lookback:]
    recent_low = low.iloc[-lookback:]
    mid = lookback // 2

    first_half_high = recent_high.iloc[:mid].max()
    second_half_high = recent_high.iloc[mid:].max()
    first_half_low = recent_low.iloc[:mid].min()
    second_half_low = recent_low.iloc[mid:].min()

    hh = second_half_high > first_half_high
    hl = second_half_low > first_half_low
    lh = second_half_high < first_half_high
    ll = second_half_low < first_half_low

    if hh and hl:
        return 80.0
    if lh and ll:
        return 20.0
    if hh or hl:
        return 65.0
    if lh or ll:
        return 35.0
    return 50.0
