from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from hl_scalper.config import Settings
from hl_scalper.strategy import Signal


class LiveTradingDisabled(RuntimeError):
    """Live Hyperliquid /exchange is not available in this lab phase."""


@dataclass(frozen=True)
class Fill:
    fill_id: str
    coin: str
    side: str
    qty: float
    px: float
    fee_usd: float
    status: str
    reason: str
    created_at: datetime


class ExecutionPort(Protocol):
    def submit(self, signal: Signal, notional_usd: float) -> Fill: ...


class PaperExecutor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def submit(self, signal: Signal, notional_usd: float) -> Fill:
        size = min(notional_usd, self.settings.max_notional_usd)
        # Adverse: buy lifts ask half-spread into mid; sell hits bid.
        slip = signal.spread_bps / 20_000.0  # quarter-spread in price terms approx
        px = signal.mid * (1.0 + slip) if signal.side == "buy" else signal.mid * (1.0 - slip)
        qty = size / px if px > 0 else 0.0
        fee = size * (self.settings.taker_fee_bps / 10_000.0)
        return Fill(
            fill_id=str(uuid4()),
            coin=signal.coin,
            side=signal.side,
            qty=qty,
            px=px,
            fee_usd=fee,
            status="paper_fill",
            reason="paper_sim",
            created_at=datetime.now(UTC),
        )


class LiveExecutor:
    """Phase 4 placeholder. Always refuses — even if settings.live_enabled is True."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def submit(self, signal: Signal, notional_usd: float) -> Fill:
        del signal, notional_usd
        raise LiveTradingDisabled(
            "HL live trading is disabled in trader_bot Phase 0–3. "
            "Paper only. Do not wire keys here."
        )


def build_executor(settings: Settings, *, mode: str) -> ExecutionPort:
    if mode == "live":
        return LiveExecutor(settings)
    return PaperExecutor(settings)
