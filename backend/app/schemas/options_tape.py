"""Aggressive options tape API schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.equity_setups import ExecutionPlanSchema, OptionCandidateSchema

DirectionBias = Literal["long", "short"]
Heat = Literal["hot", "warm"]


class TapeHuntSchema(BaseModel):
    """One aggressive long or short hunt."""

    id: str
    symbol: str
    direction: DirectionBias
    heat: Heat
    hunt_score: float = Field(..., ge=0, le=100)
    relative_volume: float
    range_expansion: float
    ret_5d_pct: float
    ret_20d_pct: float
    put_call_vol: float
    option_volume: int
    unusual_vol_oi: float
    factors: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    selected_option: OptionCandidateSchema | None = None
    option_candidates: list[OptionCandidateSchema] = Field(default_factory=list)
    execution_plan: ExecutionPlanSchema | None = None
    as_of: datetime


class TapeBoardResponse(BaseModel):
    """Balanced long/short options tape."""

    longs: list[TapeHuntSchema] = Field(default_factory=list)
    shorts: list[TapeHuntSchema] = Field(default_factory=list)
    symbols_scanned: int = 0
    symbols_optioned: int = 0
    per_side: int = 5
    scanned_at: datetime
    note: str = ""
