"""Cortex episodic and semantic ORM models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class CortexEpisodeModel(Base):
    """One persisted cortex tick (working-memory snapshot)."""

    __tablename__ = "cortex_episodes"

    tick_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    as_of: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    primed: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    triggering: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    phase: Mapped[str] = mapped_column(String(32), nullable=False, default="cortex_v2")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class CortexSemanticStatModel(Base):
    """Consolidated lead-time and calibration stats from episodic ticks."""

    __tablename__ = "cortex_semantic_stats"
    __table_args__ = (
        UniqueConstraint(
            "metric",
            "signal",
            "score_bucket",
            name="uq_cortex_semantic_metric_signal_bucket",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    metric: Mapped[str] = mapped_column(String(32), nullable=False)
    signal: Mapped[str] = mapped_column(String(64), nullable=False)
    score_bucket: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    median_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    hit_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
