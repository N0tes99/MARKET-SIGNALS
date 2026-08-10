"""Health check response schemas."""

from pydantic import BaseModel, Field


class StoreBackends(BaseModel):
    """Which persistence backends are active (postgres vs memory)."""

    learning: str = Field(..., description="Learning/outcome signal store backend")
    paper: str = Field(..., description="Paper-agent trade store backend")
    alerts: str = Field(..., description="Discord alert cooldown/snapshot store backend")


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
