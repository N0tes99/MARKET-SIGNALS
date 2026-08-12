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
