from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Fill:
    fill_id: str
    coin: str
    side: str
    qty: float
    px: float
    fee_usd: float
    status: str
    reason: str
    created_at: datetime
