"""Breakout trigger on lower timeframe with volume confirmation."""

from __future__ import annotations

import pandas as pd

from app.engines.expansion_engine.config import ExpansionConfig, default_expansion_config
from app.engines.expansion_engine.types import DirectionBias, TriggerResult
from app.indicators.volume import calculate_volume_ratio


def analyze_trigger(
    df: pd.DataFrame,
    *,
    config: ExpansionConfig | None = None,
) -> TriggerResult:
    """Detect range break + volume spike on 15m (or configured) bars."""
    cfg = config or default_expansion_config()
    if df is None or len(df) < cfg.trigger_volume_lookback + cfg.trigger_range_lookback + 2:
        return TriggerResult(
            active=False,
            direction="neutral",
            volume_ratio=None,
            breakout_level=None,
            factors=["Insufficient bars for trigger"],
        )

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]
    price = float(close.iloc[-1])

    range_lookback = cfg.trigger_range_lookback
    prior_high = float(high.iloc[-range_lookback - 1 : -1].max())
    prior_low = float(low.iloc[-range_lookback - 1 : -1].min())

    vol_ratio_series = calculate_volume_ratio(volume, period=cfg.trigger_volume_lookback)
    volume_ratio = float(vol_ratio_series.iloc[-1])

    factors: list[str] = []
    direction: DirectionBias = "neutral"
    active = False
    breakout_level: float | None = None

    broke_up = price > prior_high
    broke_down = price < prior_low
    vol_ok = volume_ratio >= cfg.trigger_volume_mult

    if broke_up:
        direction = "up"
        breakout_level = prior_high
        factors.append(f"Broke above {prior_high:.4g} range")
    elif broke_down:
        direction = "down"
        breakout_level = prior_low
        factors.append(f"Broke below {prior_low:.4g} range")

    if vol_ok:
        factors.append(f"Volume {volume_ratio:.1f}× baseline")
    else:
        factors.append(f"Volume {volume_ratio:.1f}× — below {cfg.trigger_volume_mult}× trigger")

    if (broke_up or broke_down) and vol_ok:
        active = True
        factors.append("Trigger active — breakout + volume")
    elif broke_up or broke_down:
        factors.append("Breakout without volume confirmation")

    return TriggerResult(
        active=active,
        direction=direction,
        volume_ratio=round(volume_ratio, 2),
        breakout_level=breakout_level,
        factors=factors,
    )
