"""Health check response schemas."""

from pydantic import BaseModel, Field


class StoreBackends(BaseModel):
    """Which persistence backends are active (postgres vs memory)."""

    learning: str = Field(..., description="Learning/outcome signal store backend")
    paper: str = Field(..., description="Paper-agent trade store backend")
    alerts: str = Field(..., description="Discord alert cooldown/snapshot store backend")


class WarehouseHealth(BaseModel):
    """OHLCV warehouse fill — empty until migration 020 and live fetches."""

    backend: str
    table_present: bool
    bar_count: int
    symbol_count: int
    latest_ts: str | None = None


class AlembicHealth(BaseModel):
    """Current Alembic revision vs script head."""

    current: str | None = None
    head: str | None = None
    at_head: bool = False
    source: str = "skipped"


class HealthResponse(BaseModel):
    """Health check payload returned by the API."""

    status: str = Field(..., description="Service health status")
    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="API version")
    environment: str = Field(..., description="Deployment environment")
    stores: StoreBackends | None = Field(
        default=None,
        description="Durable store backends — postgres means state survives restarts",
    )
    warehouse: WarehouseHealth | None = Field(
        default=None,
        description="ohlcv_bars fill (postgres after 020, else in-memory)",
    )
    alembic: AlembicHealth | None = Field(
        default=None,
        description="Migration current vs head — 020 creates ohlcv_bars",
    )
