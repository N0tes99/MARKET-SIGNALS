"""Symmetric volume-first tape screen (long and short scored independently)."""

from __future__ import annotations

import pandas as pd

from app.engines.options_tape.types import TapeScreen
from app.indicators.atr import calculate_atr
from app.indicators.ema import calculate_ema
from app.utils.scoring_helpers import clamp_score, detect_higher_highs_higher_lows

_MIN_BARS = 40
_MIN_REL_VOL = 1.15
_MIN_RANGE_EXP = 1.35


def _pct_change(series: pd.Series, bars: int) -> float:
    if len(series) <= bars:
        return 0.0
    prev = float(series.iloc[-(bars + 1)])
    if prev == 0:
        return 0.0
    return ((float(series.iloc[-1]) - prev) / prev) * 100.0


def score_tape(symbol: str, ohlcv: pd.DataFrame) -> TapeScreen | None:
    """Score both sides from daily OHLCV. Quiet names are not standouts."""
    if ohlcv is None or ohlcv.empty or len(ohlcv) < _MIN_BARS:
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

    ema20_last = float(ema20.iloc[-1]) if len(ema20) else price
    ema50_last = float(ema50.iloc[-1]) if len(ema50) else price
    dist_20 = ((price - ema20_last) / ema20_last) * 100.0 if ema20_last else 0.0
    dist_50 = ((price - ema50_last) / ema50_last) * 100.0 if ema50_last else 0.0

    ret_5d = _pct_change(close, 5)
    ret_20d = _pct_change(close, 20)

    vol_avg = float(volume.iloc[-21:-1].mean()) if len(volume) >= 22 else float(volume.mean())
    rel_vol = float(volume.iloc[-1]) / vol_avg if vol_avg > 0 else 1.0

    today_range = float(high.iloc[-1] - low.iloc[-1])
    range_exp = today_range / atr_last if atr_last > 0 else 1.0

    look = min(20, len(high))
    high20 = float(high.iloc[-look:-1].max()) if look > 2 else price
    low20 = float(low.iloc[-look:].min())
    dist_high = ((high20 - price) / price) * 100.0 if price else 0.0
    dist_low = ((price - low20) / price) * 100.0 if price else 0.0
    structure = detect_higher_highs_higher_lows(high, low, lookback=20)

    vol_mult = clamp_score(0.45 + rel_vol * 0.55, 0.35, 2.3)
    standout = rel_vol >= _MIN_REL_VOL or range_exp >= _MIN_RANGE_EXP

    long_raw = 50.0
    long_raw += clamp_score(ret_5d * 2.4, -16, 16)
    long_raw += clamp_score(ret_20d * 0.85, -12, 12)
    long_raw += clamp_score((3.2 - dist_high) * 2.4, -8, 12)
    long_raw += clamp_score((range_exp - 1.0) * 8.0, -6, 12)
    long_raw += (structure - 50.0) * 0.28
    long_score = clamp_score(50.0 + (long_raw - 50.0) * vol_mult)

    short_raw = 50.0
    short_raw += clamp_score(-ret_5d * 2.4, -16, 16)
    short_raw += clamp_score(-ret_20d * 0.85, -12, 12)
    short_raw += clamp_score((3.2 - dist_low) * 2.4, -8, 12)
    short_raw += clamp_score((range_exp - 1.0) * 8.0, -6, 12)
    short_raw += (50.0 - structure) * 0.28
    short_score = clamp_score(50.0 + (short_raw - 50.0) * vol_mult)

    factors: list[str] = []
    conflicts: list[str] = []
    if rel_vol >= 2.0:
        factors.append(f"Volume spike {rel_vol:.1f}×")
    elif rel_vol >= 1.4:
        factors.append(f"Relative volume {rel_vol:.1f}×")
    elif rel_vol < 0.75:
        conflicts.append(f"Volume light ({rel_vol:.1f}×)")

    if range_exp >= 1.6:
        factors.append(f"Range expansion {range_exp:.1f}× ATR")
    if atr_pct >= 4.0:
        factors.append(f"ATR {atr_pct:.1f}%")

    if ret_5d >= 3.0:
        factors.append(f"5D +{ret_5d:.1f}%")
    elif ret_5d <= -3.0:
        factors.append(f"5D {ret_5d:.1f}%")

    if 0 <= dist_high <= 2.5:
        factors.append(f"Pressing 20D high ${high20:.2f}")
    if 0 <= dist_low <= 2.5:
        factors.append(f"Pressing 20D low ${low20:.2f}")

    return TapeScreen(
        symbol=symbol.upper(),
        price=round(price, 4),
        ret_5d_pct=round(ret_5d, 2),
        ret_20d_pct=round(ret_20d, 2),
        dist_20dma_pct=round(dist_20, 2),
        dist_50dma_pct=round(dist_50, 2),
        relative_volume=round(rel_vol, 2),
        range_expansion=round(range_exp, 2),
        atr_pct=round(atr_pct, 2),
        structure_score=round(structure, 2),
        dist_20d_high_pct=round(dist_high, 2),
        dist_20d_low_pct=round(dist_low, 2),
        breakout_level=round(high20, 4),
        support_level=round(low20, 4),
        long_score=long_score,
        short_score=short_score,
        standout=standout,
        factors=factors,
        conflicts=conflicts,
    )
