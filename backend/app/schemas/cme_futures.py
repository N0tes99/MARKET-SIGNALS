"""CME / traditional futures board schemas — Yahoo continuous contracts."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

CmeFuturesBucket = Literal["trending", "extended", "quiet"]
CmeFuturesGroup = Literal["index", "energy", "metals", "rates", "fx", "grains", "crypto"]
CmeCotEffect = Literal["strengthen", "weaken", "neutral"]


class CmeFuturesUniverseItem(BaseModel):
    """One contract in the scanned universe."""

    symbol: str
    name: str
    group: CmeFuturesGroup


class CmeFuturesRowSchema(BaseModel):
    """One Yahoo continuous futures row."""

    id: str
    symbol: str
    name: str
    group: CmeFuturesGroup
    bucket: CmeFuturesBucket
    score: float = Field(..., ge=0, le=100)
    last: float | None = None
    change_pct: float | None = None
    volume: float | None = None
    open_interest: float | None = None
    expiry: date | None = None
    mom_12h_pct: float | None = None
    mom_20d_pct: float | None = None
    relative_volume: float | None = None
    factors: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    as_of: datetime
    cot_index: float | None = None
    cot_as_of: date | None = None
    cot_spec_net: float | None = None
    cot_effect: CmeCotEffect | None = None


class CmeFuturesBoardSchema(BaseModel):
    """Full CME futures scan of the Yahoo continuous universe."""

    rows: list[CmeFuturesRowSchema] = Field(default_factory=list)
    scanned_at: datetime
    symbols_scanned: int = 0
    universe: list[CmeFuturesUniverseItem] = Field(default_factory=list)
    source: str = "yahoo"
