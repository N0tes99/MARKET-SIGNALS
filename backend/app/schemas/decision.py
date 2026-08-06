"""Decision pipeline result schemas."""

from pydantic import BaseModel, Field

from app.schemas.evidence import EvidenceBundleSchema


class ExecutionSchema(BaseModel):
    """Execution timing recommendation."""

    signal: str = Field(..., description="WAIT, WATCH, or EXECUTE")
    confidence: float = Field(..., ge=0, le=100)
    description: str


class RiskSchema(BaseModel):
    """Risk parameters for a potential trade."""

    position_size: float
    stop_loss: float
    take_profit: float
    max_drawdown: float
    risk_percent: float
    risk_reward_ratio: float
    score: float
    description: str


class DecisionSchema(BaseModel):
    """Full decision pipeline output for an asset."""

    symbol: str
    evidence: EvidenceBundleSchema
    opportunity_score: float = Field(..., ge=0, le=100)
    trade_grade: str
    expected_value: float
    trade_state: str
    execution: ExecutionSchema
    risk: RiskSchema | None = None
    summary: str
    data_degraded: bool = False
    data_age_seconds: float | None = None
    data_stale_reason: str | None = None
