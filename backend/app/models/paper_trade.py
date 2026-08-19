"""Paper trade ORM model for durable public paper-agent PnL."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class PaperTradeModel(Base):
    """Persisted paper trade with optimistic + honest ledgers."""

    __tablename__ = "paper_trades"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    symbol: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    setup_type: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    signal_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    opportunity_score: Mapped[float] = mapped_column(Float, nullable=False)
    size_usd: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    optimistic_entry: Mapped[float] = mapped_column(Float, nullable=False)
    optimistic_entry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    optimistic_exit: Mapped[float | None] = mapped_column(Float, nullable=True)
    optimistic_pnl_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    optimistic_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    honest_entry: Mapped[float | None] = mapped_column(Float, nullable=True)
    honest_entry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    honest_bar_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    honest_exit: Mapped[float | None] = mapped_column(Float, nullable=True)
    honest_pnl_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    honest_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    mark_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    factors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    take_profit_pct: Mapped[float] = mapped_column(Float, nullable=False, default=6.0)
    stop_loss_pct: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    stamp: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    signal_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class PaperAgentStateModel(Base):
    """Singleton-ish key/value for paper agent process metadata."""

    __tablename__ = "paper_agent_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
