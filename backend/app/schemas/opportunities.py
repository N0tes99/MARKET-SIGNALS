"""Opportunity-related response schemas."""

from pydantic import BaseModel, Field


class OpportunitySummary(BaseModel):
    """Ranked opportunity for a single asset."""

    symbol: str = Field(..., description="Asset ticker symbol")
    opportunity_score: float = Field(..., ge=0, le=100, description="Composite opportunity score")
    trade_grade: str = Field(..., description="Letter grade for trade quality")
    expected_value: float = Field(..., description="Expected value of the opportunity")
    trade_state: str = Field(
        ...,
        description="Current trade state: IGNORE, WATCH, EXECUTE, MANAGE, or EXIT",
    )
