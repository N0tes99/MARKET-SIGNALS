from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from hl_scalper.types import Fill
from hl_scalper.feed import L2Book
from hl_scalper.strategy import Side, StrategyParams, evaluate

ExitReason = Literal["hold_expired", "imbalance_flip", "adverse_mid", "manual", "kill"]


@dataclass
class PaperPosition:
    fill: Fill
    entry_mid: float
    opened_at: datetime
    hold_seconds: float
    entry_imbalance: float = 0.5

    @property
    def side(self) -> Side:
        return self.fill.side  # type: ignore[return-value]

    def age_seconds(self, now: datetime | None = None) -> float:
        now = now or datetime.now(UTC)
        return (now - self.opened_at).total_seconds()

    def expired(self, now: datetime | None = None) -> bool:
        return self.age_seconds(now) >= self.hold_seconds


@dataclass(frozen=True)
class ClosedTrade:
    fill_id: str
    coin: str
    side: str
    qty: float
    entry_px: float
    exit_px: float
    entry_fee_usd: float
    exit_fee_usd: float
    pnl_usd: float
    hold_seconds: float
    reason: ExitReason


@dataclass(frozen=True)
class ExitDecision:
    should_exit: bool
    reason: ExitReason | None
    exit_mid: float | None


def mark_pnl(
    *,
    side: str,
    qty: float,
    entry_px: float,
    exit_px: float,
    entry_fee_usd: float,
    exit_fee_usd: float,
) -> float:
    if side == "buy":
        gross = (exit_px - entry_px) * qty
    else:
        gross = (entry_px - exit_px) * qty
    return gross - entry_fee_usd - exit_fee_usd


def adverse_mid_bps(side: str, entry_mid: float, mid: float) -> float:
    if entry_mid <= 0 or mid <= 0:
        return 0.0
    if side == "buy":
        return (entry_mid - mid) / entry_mid * 10_000.0
    return (mid - entry_mid) / entry_mid * 10_000.0


def decide_exit(
    position: PaperPosition,
    book: L2Book | None,
    *,
    strategy: StrategyParams,
    adverse_bps: float,
    now: datetime | None = None,
) -> ExitDecision:
    """Exit on time, imbalance flip against us, or adverse mid move."""
    now = now or datetime.now(UTC)
    mid = book.mid if book is not None else None
    exit_mid = mid if mid is not None else position.entry_mid

    if position.expired(now):
        return ExitDecision(True, "hold_expired", exit_mid)

    if book is None or mid is None:
        return ExitDecision(False, None, None)

    adv = adverse_mid_bps(position.fill.side, position.entry_mid, mid)
    if adv >= adverse_bps:
        return ExitDecision(True, "adverse_mid", mid)

    signal = evaluate(book, strategy)
    if signal is None:
        # Book no longer imbalanced our way — inventory risk; flat.
        # Only flip-exit after a small minimum hold to avoid noise.
        if position.age_seconds(now) >= min(1.0, position.hold_seconds):
            return ExitDecision(True, "imbalance_flip", mid)
        return ExitDecision(False, None, mid)

    if signal.side != position.fill.side and position.age_seconds(now) >= min(1.0, position.hold_seconds):
        return ExitDecision(True, "imbalance_flip", mid)

    return ExitDecision(False, None, mid)


def close_at_mid(
    position: PaperPosition,
    exit_mid: float,
    *,
    exit_fee_bps: float,
    reason: ExitReason = "hold_expired",
    now: datetime | None = None,
) -> ClosedTrade:
    """Legacy mid-mark close. Prefer ``close_from_fill`` for HL-realistic PnL."""
    now = now or datetime.now(UTC)
    notional = position.fill.qty * exit_mid
    exit_fee = notional * (exit_fee_bps / 10_000.0)
    pnl = mark_pnl(
        side=position.fill.side,
        qty=position.fill.qty,
        entry_px=position.fill.px,
        exit_px=exit_mid,
        entry_fee_usd=position.fill.fee_usd,
        exit_fee_usd=exit_fee,
    )
    return ClosedTrade(
        fill_id=position.fill.fill_id,
        coin=position.fill.coin,
        side=position.fill.side,
        qty=position.fill.qty,
        entry_px=position.fill.px,
        exit_px=exit_mid,
        entry_fee_usd=position.fill.fee_usd,
        exit_fee_usd=exit_fee,
        pnl_usd=pnl,
        hold_seconds=(now - position.opened_at).total_seconds(),
        reason=reason,
    )


def close_from_fill(
    position: PaperPosition,
    close_fill: Fill,
    *,
    reason: ExitReason = "hold_expired",
    now: datetime | None = None,
) -> ClosedTrade:
    """PnL from actual executor fill prices/fees (paper IOC sim or live HL)."""
    now = now or datetime.now(UTC)
    qty = min(position.fill.qty, close_fill.qty)
    pnl = mark_pnl(
        side=position.fill.side,
        qty=qty,
        entry_px=position.fill.px,
        exit_px=close_fill.px,
        entry_fee_usd=position.fill.fee_usd,
        exit_fee_usd=close_fill.fee_usd,
    )
    return ClosedTrade(
        fill_id=position.fill.fill_id,
        coin=position.fill.coin,
        side=position.fill.side,
        qty=qty,
        entry_px=position.fill.px,
        exit_px=close_fill.px,
        entry_fee_usd=position.fill.fee_usd,
        exit_fee_usd=close_fill.fee_usd,
        pnl_usd=pnl,
        hold_seconds=(now - position.opened_at).total_seconds(),
        reason=reason,
    )
