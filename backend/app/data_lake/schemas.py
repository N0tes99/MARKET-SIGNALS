"""Canonical schemas for warehouse tables (Phase B)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OhlcvBar:
    symbol: str
    timeframe: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class DerivativesSnapshot:
    symbol: str
    ts: datetime
    funding_rate: float
    open_interest: float
