"""Alpaca read-only mirror API schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class AlpacaAccountSchema(BaseModel):
    equity: float
    cash: float
    buying_power: float
    portfolio_value: float
    status: str
    currency: str = "USD"


class AlpacaPositionSchema(BaseModel):
    symbol: str
    qty: float
    side: str
    market_value: float
    cost_basis: float
    unrealized_pl: float
    unrealized_plpc: float
    current_price: float
    avg_entry_price: float
    change_today: float = 0.0


class AlpacaFillSchema(BaseModel):
    id: str
    symbol: str
    side: str
    qty: float
    filled_avg_price: float | None = None
    filled_at: datetime | None = None
    status: str
    order_type: str = ""
    notional: float | None = None


class AlpacaMirrorSchema(BaseModel):
    """Read-only Alpaca book vs paper — never includes execution actions."""

    configured: bool
    mode: str
    base_url: str = ""
    as_of: datetime
    cached: bool = False
    error: str | None = None
    account: AlpacaAccountSchema | None = None
    positions: list[AlpacaPositionSchema] = Field(default_factory=list)
    recent_fills: list[AlpacaFillSchema] = Field(default_factory=list)


class AlpacaActivityRowSchema(BaseModel):
    """One symbol of free-tier IEX activity (not full tape)."""

    symbol: str
    last_price: float | None = None
    daily_volume: float | None = None
    change_pct: float | None = None
    daily_bar_close: float | None = None
    prev_close: float | None = None
    trade_time: datetime | None = None


class AlpacaActivitySchema(BaseModel):
    """Alpaca Basic / IEX snapshots — feed is always iex (never SIP)."""

    configured: bool
    feed: str = "iex"
    data_base_url: str = ""
    as_of: datetime
    cached: bool = False
    error: str | None = None
    symbols_requested: list[str] = Field(default_factory=list)
    rows: list[AlpacaActivityRowSchema] = Field(default_factory=list)
