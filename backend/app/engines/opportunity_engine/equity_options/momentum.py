"""Equity momentum features for Layer 3 setups."""

from __future__ import annotations

import pandas as pd

from app.engines.opportunity_engine.equity_options.types import MomentumSnapshot
from app.indicators.atr import calculate_atr
from app.indicators.ema import calculate_ema
from app.utils.scoring_helpers import clamp_score, detect_higher_highs_higher_lows


def _pct_change(series: pd.Series, bars: int) -> float:
    if len(series) <= bars:
        return 0.0
    prev = float(series.iloc[-(bars + 1)])
    if prev == 0:
        return 0.0
    return ((float(series.iloc[-1]) - prev) / prev) * 100.0


def compute_momentum(ohlcv: pd.DataFrame) -> MomentumSnapshot | None:
    """Build momentum snapshot from daily (or higher) OHLCV bars."""
    if ohlcv is None or ohlcv.empty or len(ohlcv) < 55:
        return None

    close = ohlcv["close"].astype(float)
    high = ohlcv["high"].astype(float)
    low = ohlcv["low"].astype(float)
    volume = ohlcv["volume"].astype(float)
    price = float(close.iloc[-1])
    if price <= 0:
        return None

    ema20 = calculate_ema(close, 20)
    ema50 = calculate_ema(close, 50)
    atr = calculate_atr(high, low, close, 14)
    atr_last = float(atr.iloc[-1]) if len(atr) else 0.0
    atr_pct = (atr_last / price) * 100.0 if price else 0.0

    ema20_last = float(ema20.iloc[-1])
    ema50_last = float(ema50.iloc[-1])
    dist_20 = ((price - ema20_last) / ema20_last) * 100.0 if ema20_last else 0.0
    dist_50 = ((price - ema50_last) / ema50_last) * 100.0 if ema50_last else 0.0

    ret_5d = _pct_change(close, 5)
    ret_20d = _pct_change(close, 20)

    vol_avg = float(volume.iloc[-21:-1].mean()) if len(volume) >= 22 else float(volume.mean())
    rel_vol = float(volume.iloc[-1]) / vol_avg if vol_avg > 0 else 1.0

    structure = detect_higher_highs_higher_lows(high, low, lookback=20)

    look = min(20, len(high))
    breakout = float(high.iloc[-look:-1].max()) if look > 2 else price
    support = float(low.iloc[-look:].min())

    factors: list[str] = []
    conflicts: list[str] = []

    score = 50.0
    score += clamp_score(ret_5d * 2.2, -18, 18)
    score += clamp_score(ret_20d * 0.9, -14, 14)
    score += clamp_score(dist_20 * 1.1, -12, 12)
    score += (structure - 50.0) * 0.35
    score += clamp_score((rel_vol - 1.0) * 8.0, -8, 12)

    if ret_5d > 2.0:
        factors.append(f"5D momentum {ret_5d:+.1f}%")
    elif ret_5d < -2.0:
        conflicts.append(f"5D pullback {ret_5d:+.1f}%")

    if ret_20d > 4.0:
        factors.append(f"20D trend {ret_20d:+.1f}%")
    elif ret_20d < -4.0:
        conflicts.append(f"20D trend weak {ret_20d:+.1f}%")

    if price > ema20_last > ema50_last:
        factors.append("Price > 20DMA > 50DMA")
        score += 6.0
    elif price < ema20_last < ema50_last:
        conflicts.append("Price < 20DMA < 50DMA (bearish stack)")
        score -= 6.0
    else:
        factors.append(f"Dist 20DMA {dist_20:+.1f}% / 50DMA {dist_50:+.1f}%")

    if rel_vol >= 1.5:
        factors.append(f"Relative volume {rel_vol:.1f}×")
    elif rel_vol < 0.7:
        conflicts.append(f"Volume light ({rel_vol:.1f}×)")

    if atr_pct >= 3.5:
        factors.append(f"ATR expanded {atr_pct:.1f}%")
    elif atr_pct < 1.2:
        conflicts.append("Volatility compressed — breakout fuel unclear")

    distance_to_breakout = ((breakout - price) / price) * 100.0 if breakout else 0.0
    if 0 <= distance_to_breakout <= 3.0:
        factors.append(f"Within {distance_to_breakout:.1f}% of {look}D high ${breakout:.2f}")
        score += 5.0

    return MomentumSnapshot(
        price=price,
        ret_5d_pct=round(ret_5d, 2),
        ret_20d_pct=round(ret_20d, 2),
        dist_20dma_pct=round(dist_20, 2),
        dist_50dma_pct=round(dist_50, 2),
        relative_volume=round(rel_vol, 2),
        atr_pct=round(atr_pct, 2),
        structure_score=round(structure, 2),
        momentum_score=clamp_score(score),
        breakout_level=round(breakout, 4),
        support_level=round(support, 4),
        factors=factors,
        conflicts=conflicts,
    )
