"""Fee / latency helpers for paper fills (expanded in Phase 1–2)."""

from __future__ import annotations


def taker_fee_usd(notional: float, fee_bps: float) -> float:
    return notional * (fee_bps / 10_000.0)
