"""Volatility and range compression detector."""

from __future__ import annotations

import pandas as pd

from app.engines.expansion_engine.config import ExpansionConfig, default_expansion_config
from app.engines.expansion_engine.types import CompressionResult
from app.indicators.atr import calculate_atr
from app.utils.scoring_helpers import clamp_score


def _percentile_rank(series: pd.Series, value: float) -> float:
    """Percentile rank 0–100 (lower = value is smaller vs history)."""
    if series.empty:
        return 50.0
    return float((series <= value).mean() * 100.0)


def _bollinger_width(close: pd.Series, window: int = 20) -> pd.Series:
    mid = close.rolling(window).mean()
    std = close.rolling(window).std()
    upper = mid + 2 * std
    lower = mid - 2 * std
    width = (upper - lower) / mid.replace(0, pd.NA)
    return width.fillna(0.0)


def analyze_compression(
    df: pd.DataFrame,
    *,
    config: ExpansionConfig | None = None,
) -> CompressionResult | None:
    """Score compression from hourly (or higher) OHLCV."""
    cfg = config or default_expansion_config()
    if df is None or len(df) < cfg.compression_min_bars:
        return None

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    atr = calculate_atr(high, low, close)
    atr_pct = (atr / close.replace(0, pd.NA)).fillna(0.0)
    lookback = cfg.compression_lookback
    atr_window = atr_pct.iloc[-lookback:]
    current_atr_pct = float(atr_pct.iloc[-1])
    atr_percentile = _percentile_rank(atr_window, current_atr_pct)

    bb_width = _bollinger_width(close, window=lookback)
    bb_window = bb_width.iloc[-lookback:]
    current_bb = float(bb_width.iloc[-1])
    bb_width_percentile = _percentile_rank(bb_window, current_bb)

    price = float(close.iloc[-1])

    # Compare recent 4-bar range vs prior lookback average range
    recent_range = (high.iloc[-4:] - low.iloc[-4:]).mean() / price if price > 0 else 0.0
    hl_range = high.iloc[-lookback:] - low.iloc[-lookback:]
    avg_bar_range = float(hl_range.mean()) / price if price > 0 else 0.0
    if avg_bar_range > 0:
        range_compression_pct = clamp_score((1.0 - recent_range / avg_bar_range) * 100.0)
    else:
        range_compression_pct = 50.0

    vol_slice = volume.iloc[-lookback:-4] if len(volume) > lookback else volume
    vol_mean = float(vol_slice.mean())
    vol_recent = float(volume.iloc[-4:].mean())
    if vol_mean > 0:
        vol_ratio = vol_recent / vol_mean
        volume_compression_pct = clamp_score((1.0 - min(vol_ratio, 2.0) / 2.0) * 100.0)
    else:
        volume_compression_pct = 50.0

    factors: list[str] = []
    # Lower ATR percentile = more compressed = higher score
    atr_score = clamp_score(100.0 - atr_percentile)
    bb_score = clamp_score(100.0 - bb_width_percentile)
    range_score = range_compression_pct
    vol_score = volume_compression_pct

    factors.append(f"ATR percentile {atr_percentile:.0f}%")
    factors.append(f"BB width percentile {bb_width_percentile:.0f}%")
    factors.append(f"Range compression {range_compression_pct:.0f}%")
    if volume_compression_pct >= 60:
        factors.append(f"Volume compression {volume_compression_pct:.0f}%")

    raw = atr_score * 0.35 + bb_score * 0.25 + range_score * 0.25 + vol_score * 0.15
    score = clamp_score(raw)

    if atr_percentile <= cfg.compression_high_atr_pctile:
        factors.append("Extreme volatility compression")
    elif atr_percentile <= cfg.compression_primedd_atr_pctile:
        factors.append("Volatility compressed — spring coiling")

    return CompressionResult(
        score=score,
        atr_percentile=round(atr_percentile, 1),
        bb_width_percentile=round(bb_width_percentile, 1),
        range_compression_pct=round(range_compression_pct, 1),
        volume_compression_pct=round(volume_compression_pct, 1),
        factors=factors,
    )
