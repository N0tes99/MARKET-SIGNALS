"""Historical replay — lead time vs paper v2 momentum gate."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.engines.expansion_engine.compression import analyze_compression
from app.engines.expansion_engine.config import ExpansionConfig, default_expansion_config
from app.engines.expansion_engine.squeeze_fuel import analyze_squeeze_fuel
from app.engines.expansion_engine.state import resolve_state
from app.engines.expansion_engine.trigger import analyze_trigger
from app.engines.expansion_engine.types import ExpansionState


@dataclass(frozen=True)
class ReplayEvent:
    """One labeled expansion window."""

    symbol: str
    expansion_start_idx: int
    max_move_pct: float
    primed_idx: int | None
    triggering_idx: int | None
    v2_first_idx: int | None
    primed_hours_before_move: int | None
    v2_hours_after_move_start: int | None
    primed_before_v2: bool | None


def _find_expansion_origin(closes: pd.Series, forward_bars: int = 24) -> tuple[int, float]:
    """Bar index with best forward return over ``forward_bars``."""
    best_idx, best_move = 0, 0.0
    n = len(closes)
    for i in range(n - forward_bars):
        start = float(closes.iloc[i])
        if start <= 0:
            continue
        peak = float(closes.iloc[i : i + forward_bars].max())
        move = (peak / start - 1.0) * 100.0
        if move > best_move:
            best_move, best_idx = move, i
    return best_idx, best_move


def _momentum_at(closes: pd.Series, idx: int, bars: int = 12) -> float | None:
    if idx < bars:
        return None
    start = float(closes.iloc[idx - bars])
    end = float(closes.iloc[idx])
    if start <= 0:
        return None
    return (end / start - 1.0) * 100.0


def _state_at_bar(
    df: pd.DataFrame,
    idx: int,
    *,
    config: ExpansionConfig,
) -> tuple[ExpansionState, float | None]:
    """Evaluate expansion state using only data up to ``idx`` (inclusive)."""
    window = df.iloc[: idx + 1].copy()
    if len(window) < config.compression_min_bars:
        return ExpansionState.DORMANT, None

    compression = analyze_compression(window, config=config)
    mom = _momentum_at(window["close"], len(window) - 1, bars=12)

    squeeze = analyze_squeeze_fuel(
        compression=compression,
        depth=None,
        price=float(window["close"].iloc[-1]),
        recent_momentum_pct=mom,
        config=config,
    )
    trigger = analyze_trigger(window, config=config)
    state = resolve_state(
        compression=compression,
        squeeze=squeeze,
        trigger=trigger,
        mom_12h_pct=mom,
        config=config,
    )
    return state, mom


def replay_symbol(
    df: pd.DataFrame,
    symbol: str,
    *,
    config: ExpansionConfig | None = None,
    v2_min_momentum_pct: float = 1.5,
    forward_bars: int = 24,
    lookback_bars: int = 24,
) -> ReplayEvent | None:
    """Measure PRIMED lead time before expansion vs paper v2 momentum gate."""
    cfg = config or default_expansion_config()
    if df is None or len(df) < cfg.compression_min_bars + forward_bars + 5:
        return None

    closes = df["close"]
    start_idx, max_move = _find_expansion_origin(closes, forward_bars=forward_bars)
    if max_move < 5.0:
        return None

    primed_idx: int | None = None
    triggering_idx: int | None = None
    v2_first_idx: int | None = None

    # Look backward from move start for PRIMED / TRIGGERING
    back_start = max(cfg.compression_min_bars, start_idx - lookback_bars)
    for idx in range(start_idx, back_start - 1, -1):
        state, _mom = _state_at_bar(df, idx, config=cfg)
        if triggering_idx is None and state in {
            ExpansionState.TRIGGERING,
            ExpansionState.EXPANDING,
        }:
            triggering_idx = idx
        if primed_idx is None and state in {
            ExpansionState.PRIMED,
            ExpansionState.TRIGGERING,
            ExpansionState.EXPANDING,
        }:
            primed_idx = idx

    # Look forward from move start for v2 momentum gate
    end_idx = min(start_idx + forward_bars, len(df) - 1)
    for idx in range(start_idx, end_idx + 1):
        mom = _momentum_at(closes, idx, bars=12)
        if v2_first_idx is None and mom is not None and mom >= v2_min_momentum_pct:
            v2_first_idx = idx

    primed_hours_before = (start_idx - primed_idx) if primed_idx is not None else None
    v2_hours_after = (v2_first_idx - start_idx) if v2_first_idx is not None else None
    primed_before_v2: bool | None = None
    if primed_idx is not None and v2_first_idx is not None:
        primed_before_v2 = primed_idx <= v2_first_idx and (v2_first_idx - primed_idx) >= 2

    return ReplayEvent(
        symbol=symbol.upper(),
        expansion_start_idx=start_idx,
        max_move_pct=round(max_move, 2),
        primed_idx=primed_idx,
        triggering_idx=triggering_idx,
        v2_first_idx=v2_first_idx,
        primed_hours_before_move=primed_hours_before,
        v2_hours_after_move_start=v2_hours_after,
        primed_before_v2=primed_before_v2,
    )


def replay_universe(
    market,
    symbols: tuple[str, ...],
    *,
    config: ExpansionConfig | None = None,
) -> list[ReplayEvent]:
    """Replay benchmark symbols using 1h OHLCV from market data service."""
    cfg = config or default_expansion_config()
    events: list[ReplayEvent] = []
    for sym in symbols:
        df = market.safe_get_ohlcv(sym, "1h", limit=200)
        if df is None:
            continue
        event = replay_symbol(df, sym, config=cfg)
        if event is not None:
            events.append(event)
    return events
