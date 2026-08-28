"""Outcome labels from a price path — used after the fact, never as features."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from app.engines.runner_engine.backtest.dataset import MULTIPLES


def bar_date(ts: object) -> date:
    """UTC calendar date of an OHLCV timestamp."""
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        t = t.tz_convert("UTC")
    return t.date()


def truncate_to(df: pd.DataFrame, as_of: date) -> pd.DataFrame:
    """Keep bars with timestamp date <= as_of. Empty if none."""
    if df is None or df.empty or "timestamp" not in df.columns:
        return pd.DataFrame()
    mask = df["timestamp"].map(bar_date) <= as_of
    return df.loc[mask].copy().reset_index(drop=True)


@dataclass(frozen=True)
class MultipleLabels:
    """2×/3×/5×/10× hits measured from a trough in the first 40% of the series."""

    trough_idx: int | None
    trough_date: date | None
    trough_close: float | None
    hit_idx: dict[int, int | None]
    hit_date: dict[int, date | None]
    hit_2x: bool
    hit_5x: bool
    hit_10x: bool


def label_multiples(df: pd.DataFrame) -> MultipleLabels:
    """Find a trough, then first closes that print N×. Not a trading signal."""
    empty = MultipleLabels(
        trough_idx=None,
        trough_date=None,
        trough_close=None,
        hit_idx={n: None for n in MULTIPLES},
        hit_date={n: None for n in MULTIPLES},
        hit_2x=False,
        hit_5x=False,
        hit_10x=False,
    )
    if df is None or df.empty or len(df) < 60:
        return empty

    close = df["close"].astype(float)
    window = max(20, int(len(close) * 0.40))
    trough_idx = int(close.iloc[:window].to_numpy().argmin())
    base = float(close.iloc[trough_idx])
    if base <= 0:
        return empty

    hit_idx: dict[int, int | None] = {n: None for n in MULTIPLES}
    hit_date: dict[int, date | None] = {n: None for n in MULTIPLES}
    for n in MULTIPLES:
        target = base * n
        for i in range(trough_idx + 1, len(close)):
            if float(close.iloc[i]) >= target:
                hit_idx[n] = i
                hit_date[n] = bar_date(df["timestamp"].iloc[i])
                break

    return MultipleLabels(
        trough_idx=trough_idx,
        trough_date=bar_date(df["timestamp"].iloc[trough_idx]),
        trough_close=base,
        hit_idx=hit_idx,
        hit_date=hit_date,
        hit_2x=hit_idx[2] is not None,
        hit_5x=hit_idx[5] is not None,
        hit_10x=hit_idx[10] is not None,
    )


def max_drawdown_pct(df: pd.DataFrame, start_idx: int, end_idx: int) -> float | None:
    """Peak-to-trough % from start_idx through end_idx inclusive."""
    if df is None or df.empty:
        return None
    if start_idx < 0 or end_idx < start_idx or end_idx >= len(df):
        return None
    window = df["close"].astype(float).iloc[start_idx : end_idx + 1]
    peak = float(window.iloc[0])
    worst = 0.0
    for px in window:
        price = float(px)
        peak = max(peak, price)
        if peak > 0:
            worst = max(worst, (peak - price) / peak * 100.0)
    return round(worst, 2)


def days_between(start: date | None, end: date | None) -> int | None:
    if start is None or end is None:
        return None
    return (end - start).days
