"""Public paper-agent API schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class PaperLedgerSchema(BaseModel):
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


class PaperTradeSchema(BaseModel):
    id: str
    symbol: str
    source: str
    setup_type: str
    direction: str
    fingerprint: str
    signal_at: datetime
    confidence: float
    opportunity_score: float
    size_usd: float
    status: str
    optimistic_entry: float
    optimistic_entry_at: datetime
    optimistic_exit: float | None = None
    optimistic_pnl_usd: float | None = None
    optimistic_return_pct: float | None = None
    honest_entry: float | None = None
    honest_entry_at: datetime | None = None
    honest_bar_ts: datetime | None = None
    honest_exit: float | None = None
    honest_pnl_usd: float | None = None
    honest_return_pct: float | None = None
    mark_price: float | None = None
    closed_at: datetime | None = None
    close_reason: str | None = None
    factors: list[str] = Field(default_factory=list)
    notes: str = ""
    signal_record_id: str | None = None
    take_profit_pct: float = 6.0
    stop_loss_pct: float = 3.0
    stamp: str = ""
    policy: dict = Field(default_factory=dict)


class PaperMaturitySchema(BaseModel):
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
    blockers: list[str] = Field(default_factory=list)


class PaperSummarySchema(BaseModel):
    agent_name: str
    starting_cash: float
    as_of: datetime
    last_tick_at: datetime | None = None
    optimistic: PaperLedgerSchema
    honest: PaperLedgerSchema
    open_trades: list[PaperTradeSchema] = Field(default_factory=list)
    recent_closed: list[PaperTradeSchema] = Field(default_factory=list)
    tick_notes: list[str] = Field(default_factory=list)
    maturity: PaperMaturitySchema | None = None
    opens_today: int = 0
    daily_open_cap: int = 5
    paused_new_opens: list[str] = Field(
        default_factory=list,
        description="Idea factories not opening new paper trades (existing still manage)",
    )
