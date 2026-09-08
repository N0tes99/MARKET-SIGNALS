"""S2 maker — post-only quotes with optional two-sided inventory skew.

Live ALO posts are deferred. Paper rests join bid/ask, cancels on adverse
mid / cross / off-touch, fills when flow presses the touch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from hl_scalper.feed import L2Book
from hl_scalper.strategy import Side, Signal, notional, spread_bps

MakerOutcome = Literal["rest", "fill", "cancel"]
Inventory = Side | None  # None = flat; buy = long; sell = short


@dataclass(frozen=True)
class MakerParams:
    spread_bps_max: float = 8.0
    min_notional: float = 50_000.0
    book_levels: int = 5
    lean: float = 0.55  # directional lean for one-sided / ensemble vote
    cancel_bps: float = 4.0
    join_inside_bps: float = 0.0  # 0 = join best; >0 improves inside slightly
    twosided: bool = True


def post_only_limit(book: L2Book, side: Side, *, inside_bps: float = 0.0) -> float | None:
    """Join (or slightly improve) top of book without crossing the spread."""
    bid, ask = book.best_bid, book.best_ask
    mid = book.mid
    if bid is None or ask is None or mid is None or ask <= bid:
        return None
    if side == "buy":
        px = bid * (1.0 + inside_bps / 10_000.0) if inside_bps > 0 else bid
        return min(px, ask * (1.0 - 1e-8))
    px = ask * (1.0 - inside_bps / 10_000.0) if inside_bps > 0 else ask
    return max(px, bid * (1.0 + 1e-8))


def _book_ok(book: L2Book, p: MakerParams) -> tuple[float, float, float] | None:
    spread = spread_bps(book)
    mid = book.mid
    if spread is None or mid is None or spread > p.spread_bps_max:
        return None
    bid_n = notional(book, bids=True, levels=p.book_levels)
    ask_n = notional(book, bids=False, levels=p.book_levels)
    total = bid_n + ask_n
    if total < p.min_notional:
        return None
    return spread, mid, bid_n / total


def _maker_signal(
    book: L2Book,
    *,
    side: Side,
    imbalance: float,
    spread: float,
    mid: float,
    strength: float,
    lean: float,
    inside_bps: float,
    reason: str,
) -> Signal | None:
    limit = post_only_limit(book, side, inside_bps=inside_bps)
    if limit is None or limit <= 0:
        return None
    edge = max(0.0, min(100.0, 50.0 + (strength - lean) * 180.0 - spread * 1.5))
    return Signal(
        coin=book.coin,
        side=side,
        imbalance=imbalance,
        spread_bps=spread,
        mid=mid,
        edge_score=edge,
        reason=reason,
        execution="maker",
        limit_px=limit,
    )


def evaluate_maker(book: L2Book, params: MakerParams | None = None) -> Signal | None:
    """Directional maker join when book mildly leans (ensemble / one-sided vote)."""
    p = params or MakerParams()
    ok = _book_ok(book, p)
    if ok is None:
        return None
    spread, mid, imbalance = ok
    if imbalance >= p.lean:
        side: Side = "buy"
        strength = imbalance
    elif imbalance <= (1.0 - p.lean):
        side = "sell"
        strength = 1.0 - imbalance
    else:
        return None
    return _maker_signal(
        book,
        side=side,
        imbalance=imbalance,
        spread=spread,
        mid=mid,
        strength=strength,
        lean=p.lean,
        inside_bps=p.join_inside_bps,
        reason="maker_join",
    )


def plan_maker_quotes(
    book: L2Book,
    *,
    inventory: Inventory,
    params: MakerParams | None = None,
) -> list[Signal]:
    """Inventory-aware quote plan.

    - flat + twosided: join both bid and ask
    - flat + not twosided: directional lean only (same as evaluate_maker)
    - long: only ask (flatten / don't add)
    - short: only bid
    """
    p = params or MakerParams()
    ok = _book_ok(book, p)
    if ok is None:
        return []
    spread, mid, imbalance = ok

    def one(side: Side, reason: str, strength: float) -> Signal | None:
        return _maker_signal(
            book,
            side=side,
            imbalance=imbalance,
            spread=spread,
            mid=mid,
            strength=strength,
            lean=min(p.lean, 0.50),
            inside_bps=p.join_inside_bps,
            reason=reason,
        )

    # Inventory skew: never quote the side that increases exposure.
    if inventory == "buy":
        sig = one("sell", "maker_flatten_ask", max(imbalance, 0.55))
        return [sig] if sig else []
    if inventory == "sell":
        sig = one("buy", "maker_flatten_bid", max(1.0 - imbalance, 0.55))
        return [sig] if sig else []

    # Flat
    if not p.twosided:
        sig = evaluate_maker(book, p)
        return [sig] if sig else []

    out: list[Signal] = []
    bid = one("buy", "maker_twosided_bid", max(imbalance, 0.50))
    ask = one("sell", "maker_twosided_ask", max(1.0 - imbalance, 0.50))
    if bid:
        out.append(bid)
    if ask:
        out.append(ask)
    return out


def maker_should_cancel(
    *,
    side: Side,
    limit_px: float,
    placed_mid: float,
    book: L2Book,
    cancel_bps: float,
) -> tuple[bool, str]:
    mid = book.mid
    if mid is None:
        return True, "no_mid"
    if side == "buy" and book.best_ask is not None and limit_px >= book.best_ask:
        return True, "would_cross"
    if side == "sell" and book.best_bid is not None and limit_px <= book.best_bid:
        return True, "would_cross"
    if side == "buy" and mid > placed_mid * (1.0 + cancel_bps / 10_000.0):
        return True, "adverse_mid"
    if side == "sell" and mid < placed_mid * (1.0 - cancel_bps / 10_000.0):
        return True, "adverse_mid"
    if side == "buy" and book.best_bid is not None and limit_px < book.best_bid * 0.999:
        return True, "off_touch"
    if side == "sell" and book.best_ask is not None and limit_px > book.best_ask * 1.001:
        return True, "off_touch"
    return False, ""


def maker_should_fill(*, side: Side, limit_px: float, book: L2Book) -> bool:
    """Fill when we remain on the touch and flow presses into our quote."""
    mid = book.mid
    bid, ask = book.best_bid, book.best_ask
    if mid is None or bid is None or ask is None or mid <= 0:
        return False
    spread = (ask - bid) / mid * 10_000.0
    if side == "buy":
        on_touch = abs(bid - limit_px) / limit_px * 10_000.0 <= 1.0
        sell_pressure = (mid - bid) <= (ask - mid) + 1e-12 or ask <= limit_px * (
            1.0 + 2.0 / 10_000.0
        )
        return on_touch and sell_pressure and spread <= 8.0
    on_touch = abs(ask - limit_px) / limit_px * 10_000.0 <= 1.0
    buy_pressure = (ask - mid) <= (mid - bid) + 1e-12 or bid >= limit_px * (
        1.0 - 2.0 / 10_000.0
    )
    return on_touch and buy_pressure and spread <= 8.0
