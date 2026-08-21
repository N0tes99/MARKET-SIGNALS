"""Persisted OHLCV warehouse bars."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class OhlcvBarModel(Base):
    """One candle in the OHLCV warehouse."""

    __tablename__ = "ohlcv_bars"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(8), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="live")
