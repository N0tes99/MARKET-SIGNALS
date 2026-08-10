"""Alert cooldown / last-snapshot ORM — survives Render restarts."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AlertStateModel(Base):
    """Per-symbol alert cooldown + last fired snapshot."""

    __tablename__ = "alert_state"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    last_sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    trade_grade: Mapped[str] = mapped_column(String(10), nullable=False)
    trend: Mapped[str] = mapped_column(String(32), nullable=False)
    trade_state: Mapped[str] = mapped_column(String(20), nullable=False)
    execution_signal: Mapped[str] = mapped_column(String(20), nullable=False)
    expected_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
