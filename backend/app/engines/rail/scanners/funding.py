"""HL-native funding vs premium — not Bybit/OKX prints Signal Engine uses."""

from __future__ import annotations

from app.engines.rail.adapters.hyperliquid_info import HL_PERP_UNIVERSE, HyperliquidInfo
from app.engines.rail.envelope import mint_hl_envelope
from app.engines.rail.types import OpportunityEnvelope, SealedInstrument, Side
from app.utils.scoring_helpers import clamp_score

FAMILY = "funding"
# HL funding is an 8h rate. 1.2 bps + same-sign premium = HL crowding, not CEX OI.
_FUNDING_FLOOR = 0.00012
_PREMIUM_FLOOR = 0.00005


def scan_funding(info: HyperliquidInfo) -> list[tuple[OpportunityEnvelope, SealedInstrument]]:
    """Fade HL crowding when funding and premium agree. Requires both prints."""
    found: list[tuple[OpportunityEnvelope, SealedInstrument]] = []
    for ctx in info.perp_contexts(HL_PERP_UNIVERSE):
        funding = ctx.funding
        premium = ctx.premium
        if funding is None or premium is None:
            continue
        if abs(funding) < _FUNDING_FLOOR or abs(premium) < _PREMIUM_FLOOR:
            continue
        if (funding > 0 and premium <= 0) or (funding < 0 and premium >= 0):
            continue
        side: Side = "sell" if funding > 0 else "buy"
        edge = clamp_score(
            58.0 + min(abs(funding), 0.002) * 12_000.0 + min(abs(premium), 0.002) * 6_000.0
        )
        found.append(
            mint_hl_envelope(
                family=FAMILY,
                instrument_key=ctx.coin,
                market_kind="perp",
                side=side,
                edge_score=edge,
                invalidation="hl_funding",
            )
        )
    return found
