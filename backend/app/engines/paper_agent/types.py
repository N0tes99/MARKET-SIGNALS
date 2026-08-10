"""Public paper-trading agent types — auditable dual-ledger fills."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

PaperSource = Literal["crypto_setup", "equity_setup"]
PaperStatus = Literal["pending_honest", "open", "closed"]
PaperDirection = Literal["long", "short"]


@dataclass
class PaperTrade:
    """One paper trade with optimistic + next-bar (honest) ledgers."""

    id: str
    symbol: str
    source: PaperSource
    setup_type: str
    direction: PaperDirection
    fingerprint: str
    signal_at: datetime
    confidence: float
    opportunity_score: float
    size_usd: float
    status: PaperStatus

    # Optimistic: fill at signal-time last/mid
    optimistic_entry: float
    optimistic_entry_at: datetime
    optimistic_exit: float | None = None
    optimistic_pnl_usd: float | None = None
    optimistic_return_pct: float | None = None

    # Honest: fill at next bar open after signal
    honest_entry: float | None = None
    honest_entry_at: datetime | None = None
    honest_bar_ts: datetime | None = None
    honest_exit: float | None = None
    honest_pnl_usd: float | None = None
    honest_return_pct: float | None = None

    mark_price: float | None = None
    closed_at: datetime | None = None
    close_reason: str | None = None
    factors: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class PaperLedgerSnapshot:
    """One fill convention's marked performance."""

    label: str
    starting_cash: float
    equity: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    return_pct: float
    open_positions: int
    closed_trades: int
    wins: int
    losses: int


@dataclass
class PaperAgentSummary:
    """Public dashboard payload."""

    agent_name: str
    starting_cash: float
    as_of: datetime
    last_tick_at: datetime | None
    optimistic: PaperLedgerSnapshot
    honest: PaperLedgerSnapshot
    open_trades: list[PaperTrade]
    recent_closed: list[PaperTrade]
    tick_notes: list[str] = field(default_factory=list)
