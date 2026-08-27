"""HIP-4 outcome books — event contracts Signal Engine has no surface for."""

from __future__ import annotations

from app.engines.rail.adapters.hyperliquid_info import HyperliquidInfo
from app.engines.rail.envelope import mint_hl_envelope
from app.engines.rail.types import OpportunityEnvelope, SealedInstrument, Side
from app.utils.scoring_helpers import clamp_score

FAMILY = "outcome"
_GAP_FLOOR = 0.02
_MAX_OUTCOMES = 3


def _trade_coin(outcome_id: int, side: int) -> str:
    """HIP-4 /info l2Book coin. encoding = 10 * outcome + side (YES=0, NO=1)."""
    return f"#{10 * outcome_id + side}"


def _mid(info: HyperliquidInfo, coin: str) -> float | None:
    book = info.l2_book(coin)
    if book is None or book.best_bid is None or book.best_ask is None:
        return None
    return (book.best_bid + book.best_ask) / 2.0


def scan_outcomes(info: HyperliquidInfo) -> list[tuple[OpportunityEnvelope, SealedInstrument]]:
    """One-leg clerk idea when YES+NO mids drift off 1.00 on HL."""
    found: list[tuple[OpportunityEnvelope, SealedInstrument]] = []
    for spec in info.outcomes(limit=_MAX_OUTCOMES):
        yes_coin = _trade_coin(spec.outcome_id, 0)
        no_coin = _trade_coin(spec.outcome_id, 1)
        yes_mid = _mid(info, yes_coin)
        no_mid = _mid(info, no_coin)
        if yes_mid is None or no_mid is None:
            continue
        gap = yes_mid + no_mid - 1.0
        if abs(gap) < _GAP_FLOOR:
            continue
        if gap < 0:
            # Pair cheap: buy the cheaper side.
            if yes_mid <= no_mid:
                side: Side = "buy"
                key = f"HL4:{spec.outcome_id}:0"
            else:
                side = "buy"
                key = f"HL4:{spec.outcome_id}:1"
        elif yes_mid >= no_mid:
            side = "sell"
            key = f"HL4:{spec.outcome_id}:0"
        else:
            side = "sell"
            key = f"HL4:{spec.outcome_id}:1"
        edge = clamp_score(60.0 + min(abs(gap), 0.12) * 250.0)
        found.append(
            mint_hl_envelope(
                family=FAMILY,
                instrument_key=key,
                market_kind="outcome",
                side=side,
                edge_score=edge,
                invalidation="outcome_gap",
                ttl_seconds=180,
            )
        )
    return found
