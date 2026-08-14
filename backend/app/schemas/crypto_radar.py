"""Crypto Radar API schemas — Watch / Crowded / Running."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

CryptoRadarBucket = Literal["watch", "crowded", "running", "none"]


class CryptoRadarCandidateSchema(BaseModel):
    """One crypto possible-move candidate."""

    id: str
    symbol: str
    bucket: CryptoRadarBucket
    score: float = Field(..., ge=0, le=100)
    factors: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    mom_12h_pct: float | None = None
    mom_20d_pct: float | None = None
    funding_bps: float | None = None
    oi_change_pct: float | None = None
    funding_source: str = ""
    mark_price: float | None = None
    as_of: datetime


class CryptoRadarFeedResponse(BaseModel):
    """Full crypto radar scan of the V2 universe."""

    candidates: list[CryptoRadarCandidateSchema] = Field(default_factory=list)
    watch: list[CryptoRadarCandidateSchema] = Field(default_factory=list)
    crowded: list[CryptoRadarCandidateSchema] = Field(default_factory=list)
    running: list[CryptoRadarCandidateSchema] = Field(default_factory=list)
    scanned_at: datetime
    symbols_scanned: int = 0
    funding_filled: int = 0
    universe: list[str] = Field(default_factory=list)
