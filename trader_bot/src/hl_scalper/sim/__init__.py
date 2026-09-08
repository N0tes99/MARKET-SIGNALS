"""Hyperliquid-realistic fee / IOC slip helpers shared by paper + live."""

from __future__ import annotations


def taker_fee_usd(notional: float, fee_bps: float) -> float:
    return abs(notional) * (fee_bps / 10_000.0)


def ioc_slip_frac(spread_bps: float, *, min_slip_bps: float = 5.0) -> float:
    """Fraction through mid for a marketable IOC limit.

    Matches live: at least ``min_slip_bps`` through mid, or the full spread if wider.
    Crossing mid by ~full spread is aggressively marketable vs top of book.
    """
    return max(float(spread_bps), float(min_slip_bps)) / 10_000.0


def ioc_limit_px(
    *,
    side: str,
    mid: float,
    spread_bps: float,
    min_slip_bps: float = 5.0,
) -> float:
    slip = ioc_slip_frac(spread_bps, min_slip_bps=min_slip_bps)
    if side == "buy":
        return mid * (1.0 + slip)
    return mid * (1.0 - slip)


def ioc_exit_limit_px(
    *,
    flatten_is_buy: bool,
    mid: float,
    min_slip_bps: float = 5.0,
) -> float:
    slip = float(min_slip_bps) / 10_000.0
    if flatten_is_buy:
        return mid * (1.0 + slip)
    return mid * (1.0 - slip)


def estimated_round_trip_bps(
    spread_bps: float,
    *,
    taker_fee_bps: float,
    fee_edge_buffer_bps: float,
    min_slip_bps: float = 5.0,
) -> float:
    """HL-realistic IOC round-trip cost in bps (entry cross + exit cross + fees + buffer)."""
    entry = max(float(spread_bps), float(min_slip_bps))
    exit_ = float(min_slip_bps)
    fees = 2.0 * float(taker_fee_bps)
    return entry + exit_ + fees + float(fee_edge_buffer_bps)


def estimated_maker_round_trip_bps(
    spread_bps: float,
    *,
    maker_fee_bps: float,
    fee_edge_buffer_bps: float,
    cancel_bps: float,
) -> float:
    """Paper maker RT: 2×maker fee + buffer + cancel/adverse budget (no IOC cross)."""
    return (
        2.0 * float(maker_fee_bps)
        + float(fee_edge_buffer_bps)
        + float(cancel_bps) * 0.5
        + float(spread_bps) * 0.25
    )
