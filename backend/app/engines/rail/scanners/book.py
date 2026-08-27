"""HL L2 imbalance — venue book Signal Engine does not have."""

from __future__ import annotations

from app.engines.rail.adapters.hyperliquid_info import HL_PERP_UNIVERSE, HyperliquidInfo, L2Book
from app.engines.rail.envelope import mint_hl_envelope
from app.engines.rail.types import OpportunityEnvelope, SealedInstrument, Side
from app.utils.scoring_helpers import clamp_score

FAMILY = "book"
_IMBALANCE_MIN = 0.72
_SPREAD_BPS_MAX = 12.0
_MIN_NOTIONAL = 50_000.0
_LEVELS = 5


def _notional(book: L2Book, *, bids: bool) -> float:
    levels = book.bids[:_LEVELS] if bids else book.asks[:_LEVELS]
    return sum(level.px * level.sz for level in levels)


def _spread_bps(book: L2Book) -> float | None:
    bid = book.best_bid
    ask = book.best_ask
    if bid is None or ask is None or bid <= 0 or ask <= bid:
        return None
    mid = (bid + ask) / 2.0
    if mid <= 0:
        return None
    return (ask - bid) / mid * 10_000.0


def scan_books(info: HyperliquidInfo) -> list[tuple[OpportunityEnvelope, SealedInstrument]]:
    """Stacked book on HL. Buy bid-heavy, sell ask-heavy. Sit out if thin or wide."""
    found: list[tuple[OpportunityEnvelope, SealedInstrument]] = []
    for coin in HL_PERP_UNIVERSE:
        book = info.l2_book(coin)
        if book is None:
            continue
        bid_n = _notional(book, bids=True)
        ask_n = _notional(book, bids=False)
        total = bid_n + ask_n
        if total < _MIN_NOTIONAL:
            continue
        spread = _spread_bps(book)
        if spread is None or spread > _SPREAD_BPS_MAX:
            continue
        imbalance = bid_n / total
        if imbalance >= _IMBALANCE_MIN:
            side: Side = "buy"
            strength = imbalance
        elif imbalance <= (1.0 - _IMBALANCE_MIN):
            side = "sell"
            strength = 1.0 - imbalance
        else:
            continue
        edge = clamp_score(55.0 + (strength - _IMBALANCE_MIN) * 200.0 - spread * 0.8)
        found.append(
            mint_hl_envelope(
                family=FAMILY,
                instrument_key=coin,
                market_kind="perp",
                side=side,
                edge_score=edge,
                invalidation="book_imbalance",
            )
        )
    return found
