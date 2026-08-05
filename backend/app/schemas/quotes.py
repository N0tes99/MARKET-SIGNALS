"""Market quote schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class AssetQuote(BaseModel):
    """Latest price feed for a tracked asset."""

    symbol: str
    price: float | None = None
    change_pct: float | None = Field(
        default=None,
        description="Percent change vs prior close (approx session/24h)",
    )
    as_of: datetime | None = None
    available: bool = False
