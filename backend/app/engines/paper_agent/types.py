"""Public paper-trading agent types — auditable dual-ledger fills."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

PaperSource = Literal[
    "crypto_setup",
    "equity_setup",
    "tape_hunt",
    "crypto_perp_v2",
    "cme_futures",
    "squeeze_expansion",
]
PaperStatus = Literal["pending_honest", "open", "closing", "closed"]
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
    signal_record_id: str | None = None
    take_profit_pct: float = 6.0
    stop_loss_pct: float = 3.0
    stamp: str = ""
    # Frozen knobs + features at open (and close labels after exit).
    policy: dict[str, Any] = field(default_factory=dict)


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
    deployed_usd: float = 0.0
    size_usd: float = 0.0


@dataclass
class PaperMaturitySnapshot:
    """Training readiness toward private micro live."""

    honest_closed: int
    memory_outcomes: int
    win_rate: float
    avg_return_pct: float
    expectancy_ok: bool
    max_drawdown_pct: float
    drawdown_ok: bool
    target_honest_closed: int
    target_memory_outcomes: int
    score_pct: float
    ready_for_private_live: bool
    blockers: list[str] = field(default_factory=list)


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
    maturity: PaperMaturitySnapshot | None = None
    opens_today: int = 0
    daily_open_cap: int = 5
