from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from hl_scalper.execution import Fill
from hl_scalper.strategy import Side

ExitReason = Literal["hold_expired", "manual", "kill"]


@dataclass
class PaperPosition:
    fill: Fill
    entry_mid: float
    opened_at: datetime
    hold_seconds: float

    @property
    def side(self) -> Side:
        return self.fill.side  # type: ignore[return-value]

    def expired(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        return (now - self.opened_at).total_seconds() >= self.hold_seconds


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


def close_at_mid(
    position: PaperPosition,
    exit_mid: float,
    *,
    exit_fee_bps: float,
    reason: ExitReason = "hold_expired",
    now: datetime | None = None,
) -> ClosedTrade:
    now = now or datetime.now(UTC)
    notional = position.fill.qty * exit_mid
    exit_fee = notional * (exit_fee_bps / 10_000.0)
    # Exit slip: sell hits bid-ish, buy cover lifts ask-ish — use mid for Phase 1 marks.
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
