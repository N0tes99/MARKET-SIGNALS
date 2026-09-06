from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from hl_scalper.feed import L2Book

Side = Literal["buy", "sell"]


@dataclass(frozen=True)
class Signal:
    coin: str
    side: Side
    imbalance: float
    spread_bps: float
    mid: float
    edge_score: float
    reason: str


@dataclass(frozen=True)
class StrategyParams:
    imbalance_min: float = 0.72
    spread_bps_max: float = 12.0
    min_notional: float = 50_000.0
    book_levels: int = 5


def notional(book: L2Book, *, bids: bool, levels: int) -> float:
    side = book.bids[:levels] if bids else book.asks[:levels]
    return sum(level.px * level.sz for level in side)


def spread_bps(book: L2Book) -> float | None:
    bid, ask = book.best_bid, book.best_ask
    if bid is None or ask is None or bid <= 0 or ask <= bid:
        return None
    mid = (bid + ask) / 2.0
    if mid <= 0:
        return None
    return (ask - bid) / mid * 10_000.0


def evaluate(book: L2Book, params: StrategyParams | None = None) -> Signal | None:
    """Buy bid-heavy books, sell ask-heavy. Sit out if thin or wide."""
    p = params or StrategyParams()
    bid_n = notional(book, bids=True, levels=p.book_levels)
    ask_n = notional(book, bids=False, levels=p.book_levels)
    total = bid_n + ask_n
    if total < p.min_notional:
        return None
    spread = spread_bps(book)
    mid = book.mid
    if spread is None or mid is None or spread > p.spread_bps_max:
        return None
    imbalance = bid_n / total
    if imbalance >= p.imbalance_min:
        side: Side = "buy"
        strength = imbalance
    elif imbalance <= (1.0 - p.imbalance_min):
        side = "sell"
        strength = 1.0 - imbalance
    else:
        return None
    edge = max(0.0, min(100.0, 55.0 + (strength - p.imbalance_min) * 200.0 - spread * 0.8))
    return Signal(
        coin=book.coin,
        side=side,
        imbalance=imbalance,
        spread_bps=spread,
        mid=mid,
        edge_score=edge,
        reason="book_imbalance",
    )
