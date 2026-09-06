from __future__ import annotations

from dataclasses import dataclass

from hl_scalper.config import Settings
from hl_scalper.strategy import Signal


@dataclass
class RiskState:
    equity_usd: float
    day_pnl_usd: float = 0.0
    open_positions: int = 0
    killed: bool = False
    kill_reason: str = ""
    consecutive_losses: int = 0


@dataclass
class RiskDecision:
    allowed: bool
    reason: str


class RiskGate:
    def __init__(self, settings: Settings, state: RiskState | None = None) -> None:
        self.settings = settings
        self.state = state or RiskState(equity_usd=settings.paper_equity_usd)

    def check(self, signal: Signal, book_age_s: float) -> RiskDecision:
        if self.state.killed:
            return RiskDecision(False, f"killed:{self.state.kill_reason}")
        if book_age_s > self.settings.max_book_age_s:
            return RiskDecision(False, "stale_book")
        if self.state.open_positions >= self.settings.max_concurrent_positions:
            return RiskDecision(False, "max_positions")
        loss_limit = -self.settings.daily_loss_kill_pct * self.state.equity_usd
        if self.state.day_pnl_usd <= loss_limit:
            self.trip(f"daily_loss:{self.state.day_pnl_usd:.2f}")
            return RiskDecision(False, self.state.kill_reason)
        del signal  # size caps applied at execution sizing
        return RiskDecision(True, "ok")

    def trip(self, reason: str) -> None:
        self.state.killed = True
        self.state.kill_reason = reason

    def record_pnl(self, pnl_usd: float) -> None:
        self.state.day_pnl_usd += pnl_usd
        if pnl_usd < 0:
            self.state.consecutive_losses += 1
        else:
            self.state.consecutive_losses = 0
        loss_limit = -self.settings.daily_loss_kill_pct * self.state.equity_usd
        if self.state.day_pnl_usd <= loss_limit:
            self.trip(f"daily_loss:{self.state.day_pnl_usd:.2f}")
