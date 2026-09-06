from __future__ import annotations

import time
from dataclasses import dataclass

from hl_scalper.config import Settings
from hl_scalper.strategy import Signal


@dataclass
class RiskState:
    equity_usd: float
    day_pnl_usd: float = 0.0
    week_pnl_usd: float = 0.0
    open_positions: int = 0
    killed: bool = False
    kill_reason: str = ""
    consecutive_losses: int = 0
    cooldown_until: float = 0.0  # epoch seconds


@dataclass
class RiskDecision:
    allowed: bool
    reason: str


class RiskGate:
    """Capital-preservation gate. Sit-out is the default success mode."""

    def __init__(self, settings: Settings, state: RiskState | None = None) -> None:
        self.settings = settings
        self.state = state or RiskState(equity_usd=settings.paper_equity_usd)

    def check(self, signal: Signal, book_age_s: float) -> RiskDecision:
        if self.state.killed:
            return RiskDecision(False, f"killed:{self.state.kill_reason}")
        now = time.time()
        if now < self.state.cooldown_until:
            return RiskDecision(False, "cooldown")
        if book_age_s > self.settings.max_book_age_s:
            return RiskDecision(False, "stale_book")
        if self.state.open_positions >= self.settings.max_concurrent_positions:
            return RiskDecision(False, "max_positions")

        day_limit = -self.settings.daily_loss_kill_pct * self.state.equity_usd
        if self.state.day_pnl_usd <= day_limit:
            self.trip(f"daily_loss:{self.state.day_pnl_usd:.2f}")
            return RiskDecision(False, self.state.kill_reason)

        week_limit = -self.settings.weekly_loss_kill_pct * self.state.equity_usd
        if self.state.week_pnl_usd <= week_limit:
            self.trip(f"weekly_loss:{self.state.week_pnl_usd:.2f}")
            return RiskDecision(False, self.state.kill_reason)

        # Round-trip taker + buffer must fit inside a tight scalp budget.
        round_trip_bps = 2.0 * self.settings.taker_fee_bps + self.settings.fee_edge_buffer_bps
        cost = signal.spread_bps + round_trip_bps
        budget = self.settings.spread_bps_max + self.settings.fee_edge_buffer_bps
        if cost > budget + 1e-9:
            return RiskDecision(False, "fee_edge_block")

        if signal.coin not in self.settings.live_coins and self.settings.live_enabled:
            return RiskDecision(False, "coin_not_in_live_universe")

        return RiskDecision(True, "ok")

    def trip(self, reason: str) -> None:
        self.state.killed = True
        self.state.kill_reason = reason

    def record_pnl(self, pnl_usd: float) -> None:
        self.state.day_pnl_usd += pnl_usd
        self.state.week_pnl_usd += pnl_usd
        if pnl_usd < 0:
            self.state.consecutive_losses += 1
            if self.state.consecutive_losses >= self.settings.max_consecutive_losses:
                self.state.cooldown_until = time.time() + self.settings.cooldown_seconds
                self.state.consecutive_losses = 0
        else:
            self.state.consecutive_losses = 0

        day_limit = -self.settings.daily_loss_kill_pct * self.state.equity_usd
        if self.state.day_pnl_usd <= day_limit:
            self.trip(f"daily_loss:{self.state.day_pnl_usd:.2f}")
        week_limit = -self.settings.weekly_loss_kill_pct * self.state.equity_usd
        if self.state.week_pnl_usd <= week_limit:
            self.trip(f"weekly_loss:{self.state.week_pnl_usd:.2f}")
