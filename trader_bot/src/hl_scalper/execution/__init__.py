from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from hl_scalper.arming import check_arming
from hl_scalper.config import Settings
from hl_scalper.strategy import Signal


class LiveTradingDisabled(RuntimeError):
    """Live Hyperliquid /exchange is not available / not armed."""


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
        slip = signal.spread_bps / 20_000.0
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
    """Live path scaffold. Refuses unless every arming gate passes.

    Even when armed, `allow_live_orders` must be True before any `/exchange`
    signing is attempted. Signing itself is not wired yet (Phase 4).
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def submit(self, signal: Signal, notional_usd: float) -> Fill:
        del notional_usd
        status = check_arming(
            live_enabled=self.settings.live_enabled,
            allow_live_orders=self.settings.allow_live_orders,
            arm_file=Path(self.settings.arm_file),
            killed=False,
        )
        if not status.ok:
            raise LiveTradingDisabled(f"live not armed: {status.summary}")
        if signal.coin not in self.settings.live_coins:
            raise LiveTradingDisabled(f"coin {signal.coin} not in live universe")
        # Signing /exchange lands here in Phase 4 — still refuse until implemented.
        raise LiveTradingDisabled(
            "live gates passed but HL /exchange signer is not wired yet "
            "(Phase 4). Paper mode remains the product path."
        )


def build_executor(settings: Settings, *, mode: str) -> ExecutionPort:
    if mode == "live":
        return LiveExecutor(settings)
    return PaperExecutor(settings)
