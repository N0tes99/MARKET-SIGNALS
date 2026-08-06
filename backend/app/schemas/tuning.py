"""Weight tuning API schemas."""

from pydantic import BaseModel, Field


class WeightsMapSchema(BaseModel):
    """Category weight mapping."""

    Trend: float
    Momentum: float
    Volume: float
    Structure: float
    Risk: float
    Macro: float
    Derivatives: float


class PresetResultSchema(BaseModel):
    """Backtest result for one weight preset."""

    preset_name: str
    weights: dict[str, float]
    total_signals: int
    win_rate: float
    avg_return_pct: float
    score: float


class WeightTuningSchema(BaseModel):
    """Weight optimization response."""

    symbol: str
    timeframe: str
    active_preset: str
    active_weights: dict[str, float]
    recommended_preset: str
    recommended_weights: dict[str, float]
    results: list[PresetResultSchema]


class ApplyPresetSchema(BaseModel):
    """Request body to apply a weight preset."""

    preset: str = Field(..., description="Named preset from optimization results")


class ActiveWeightsSchema(BaseModel):
    """Currently active scoring weights."""

    preset: str
    weights: dict[str, float]
    regime_auto: bool = Field(
        default=True,
        description="True = regime profiles; false after custom/preset apply",
    )
