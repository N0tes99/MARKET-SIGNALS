"""Paper broker — dual fills (optimistic signal mid + honest next-bar open)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pandas as pd

from app.market_data.service import MarketDataService
from app.utils.scoring_helpers import clamp_score

logger = logging.getLogger(__name__)

# Fixed paper risk per idea — Risk Engine remains authority for live later
DEFAULT_SIZE_USD = 2_500.0
SLIPPAGE_BPS = 5.0  # 0.05% adverse vs reference
# Slightly tighter than the first pass so sleeves rotate on real moves.
TAKE_PROFIT_PCT = 6.0
STOP_LOSS_PCT = 3.0
MAX_HOLD_HOURS = 24 * 3


def _bps_slip(price: float, direction: str, *, entry: bool) -> float:
    """Adverse slippage in bps on entry/exit."""
    slip = price * (SLIPPAGE_BPS / 10_000.0)
    long = direction == "long"
    if entry:
        return price + slip if long else price - slip
    return price - slip if long else price + slip


def last_price(market: MarketDataService, symbol: str) -> float | None:
    try:
        ticker = market.get_ticker(symbol)
        return float(ticker.price) if ticker and ticker.price else None
    except Exception:
        logger.debug("Paper last price failed for %s", symbol, exc_info=True)
        return None


def next_bar_open_after(
    market: MarketDataService,
    symbol: str,
    signal_at: datetime,
    *,
    timeframe: str = "15m",
) -> tuple[float, datetime] | None:
    """Return (open, bar_ts) for the first bar that opens strictly after signal_at."""
    try:
        frame = market.safe_get_ohlcv(symbol, timeframe, limit=96)
    except Exception:
        logger.debug("Paper OHLCV failed for %s", symbol, exc_info=True)
        return None
    if frame is None or frame.empty or "timestamp" not in frame.columns:
        return None

    df = frame.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    signal = signal_at if signal_at.tzinfo else signal_at.replace(tzinfo=UTC)
    later = df[df["timestamp"] > signal].sort_values("timestamp")
    if later.empty:
        return None
    row = later.iloc[0]
    open_px = float(row["open"])
    bar_ts = row["timestamp"].to_pydatetime()
    if bar_ts.tzinfo is None:
        bar_ts = bar_ts.replace(tzinfo=UTC)
    return open_px, bar_ts


def unrealized_pnl(
    *,
    direction: str,
    entry: float,
    mark: float,
    size_usd: float,
) -> tuple[float, float]:
    """Return (pnl_usd, return_pct)."""
    if entry <= 0 or size_usd <= 0:
        return 0.0, 0.0
    ret = (mark - entry) / entry * 100.0 if direction == "long" else (entry - mark) / entry * 100.0
    pnl = size_usd * (ret / 100.0)
    return pnl, ret


def should_close(
    *,
    direction: str,
    entry: float,
    mark: float,
    opened_at: datetime,
    now: datetime,
) -> str | None:
    """Exit rules for MVP paper agent."""
    _, ret = unrealized_pnl(direction=direction, entry=entry, mark=mark, size_usd=1.0)
    if ret >= TAKE_PROFIT_PCT:
        return f"take_profit_+{TAKE_PROFIT_PCT:.0f}%"
    if ret <= -STOP_LOSS_PCT:
        return f"stop_loss_-{STOP_LOSS_PCT:.0f}%"
    age_h = (now - opened_at).total_seconds() / 3600.0
    if age_h >= MAX_HOLD_HOURS:
        return f"max_hold_{MAX_HOLD_HOURS}h"
    return None


def clamp_confidence(value: float) -> float:
    return clamp_score(value)
