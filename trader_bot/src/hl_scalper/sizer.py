from __future__ import annotations

from dataclasses import dataclass

from hl_scalper.config import Settings
from hl_scalper.strategy import Signal


@dataclass(frozen=True)
class SizeDecision:
    notional_usd: float
    reason: str


def size_notional(settings: Settings, signal: Signal, equity_usd: float) -> SizeDecision:
    """Cap notional by settings and a tiny equity fraction (paper-safe)."""
    del signal  # edge-aware sizing lands in Phase 2
    frac_cap = max(0.0, equity_usd * 0.01)  # 1% of equity
    notional = min(settings.max_notional_usd, frac_cap if frac_cap > 0 else settings.max_notional_usd)
    if notional < 1.0:
        return SizeDecision(0.0, "dust")
    return SizeDecision(notional, "capped")
