"""Alert API schemas."""

from pydantic import BaseModel, Field


class AlertStatusSchema(BaseModel):
    """Public alert configuration status."""

    enabled: bool
    min_confidence: float
    min_grade: str
    cooldown_minutes: int
    discord_configured: bool
    discord_mode: str = "none"
    email_configured: bool
    channels: dict[str, bool]


class AlertEventSchema(BaseModel):
    """Fired alert summary."""

    symbol: str
    confidence: float
    trade_grade: str
    trade_state: str
    execution_signal: str
    expected_value: float
    trend: str
    asset_class: str
    trigger: str = "threshold_cross"
    trigger_ref: str = ""
    prev_confidence: float | None = None
    prev_grade: str | None = None


class AlertDispatchSchema(BaseModel):
    """Result of an alert evaluation pass."""

    enabled: bool
    evaluated: int
    matched: int
    sent: int
    skipped_cooldown: int
    skipped_unchanged: int = 0
    discord_ok: bool | None = None
    email_ok: bool | None = None
    events: list[AlertEventSchema] = Field(default_factory=list)


class AlertTestRequest(BaseModel):
    """Optional channel override for test alerts."""

    channel: str = Field(default="both", pattern="^(both|discord|email)$")
