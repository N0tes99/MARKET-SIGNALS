"""Persisted scoring weight overrides — Apply survives restart."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class WeightOverrideModel(Base):
    """Single-row active weight preset (id=1)."""

    __tablename__ = "weight_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    preset: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    weights: Mapped[dict] = mapped_column(JSONB, nullable=False)
    regime_auto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
