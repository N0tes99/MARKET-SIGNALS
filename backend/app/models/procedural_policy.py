"""Versioned procedural policies (expansion knobs, later other engines)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ProceduralPolicyModel(Base):
    """One active policy row per name (``expansion``, …)."""

    __tablename__ = "procedural_policies"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    knobs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
