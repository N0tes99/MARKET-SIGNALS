"""Mint clerk-blind opportunity envelopes. Scanners may see tickers; clerk JSON may not."""

from __future__ import annotations

import hashlib
import hmac
import re
from datetime import UTC, datetime
from typing import Any

from app.config import settings
from app.engines.paper_agent.types import PaperTrade
from app.engines.rail.types import (
    CRYPTO_PAPER_SOURCES,
    EnvelopeStatus,
    MarketKind,
    OpportunityEnvelope,
    SealedInstrument,
    Side,
    SizeBand,
    Urgency,
    VenueId,
)

HANDLE_LEN = 16


def _secret() -> bytes:
    return settings.secret_key.encode("utf-8")


def instrument_handle(*, venue: str, symbol: str, market_kind: str) -> str:
    """Stable opaque handle. Adapters recompute; the clerk cannot reverse it."""
    material = f"{venue}|{symbol.upper()}|{market_kind}".encode()
    digest = hmac.new(_secret(), material, hashlib.sha256).hexdigest()
    return digest[:HANDLE_LEN]


def size_band(size_usd: float) -> SizeBand:
    if size_usd < 750:
        return "xs"
    if size_usd < 1500:
        return "s"
    if size_usd < 3500:
        return "m"
    return "l"


def urgency(confidence: float) -> Urgency:
    if confidence >= 75:
        return "aggressive"
    if confidence >= 60:
        return "normal"
    return "passive"


def invalidation_code(stop_loss_pct: float) -> str:
    band = max(1, min(9, int(round(float(stop_loss_pct)))))
    return f"stop_band_{band}"


def side_from_direction(direction: str) -> Side | None:
    if direction == "long":
        return "buy"
    if direction == "short":
        return "sell"
    return None


def envelope_status(paper_status: str) -> EnvelopeStatus:
    if paper_status in {"pending_honest", "open", "closing"}:
        return "open"
    return "closed"


def target_venue_for_source(source: str) -> VenueId:
    """Where this opportunity would rail later. Phase A still fills on paper."""
    if source in CRYPTO_PAPER_SOURCES:
        return "hyperliquid"
    return "paper"


def mint_from_paper_trade(trade: PaperTrade) -> tuple[OpportunityEnvelope, SealedInstrument] | None:
    """Strip thesis. Equity/CME/tape do not enter crypto rails."""
    if trade.source not in CRYPTO_PAPER_SOURCES:
        return None
    side = side_from_direction(trade.direction)
    if side is None:
        return None
    target = target_venue_for_source(trade.source)
    handle = instrument_handle(venue=target, symbol=trade.symbol, market_kind="perp")
    status = envelope_status(trade.status)
    ttl = 900 if status == "open" else 0
    envelope = OpportunityEnvelope(
        envelope_id=f"paper:{trade.id}",
        venue="paper",
        target_venue=target,
        market_kind="perp",
        side=side,
        size_band=size_band(trade.size_usd),
        urgency=urgency(trade.confidence),
        edge_score=float(trade.opportunity_score or trade.confidence),
        ttl_seconds=ttl,
        invalidation=invalidation_code(trade.stop_loss_pct),
        instrument_handle=handle,
        status=status,
        created_at=trade.signal_at,
    )
    sealed = SealedInstrument(
        handle=handle,
        venue=target,
        symbol=trade.symbol.upper(),
        market_kind="perp",
        paper_trade_id=trade.id,
    )
    return envelope, sealed


def mint_hl_envelope(
    *,
    family: str,
    instrument_key: str,
    market_kind: str,
    side: Side,
    edge_score: float,
    invalidation: str,
    ttl_seconds: int = 120,
    size_band: SizeBand = "xs",
    created_at: datetime | None = None,
) -> tuple[OpportunityEnvelope, SealedInstrument]:
    """Seal a Hyperliquid-native idea. instrument_key never leaves SealedInstrument."""
    kind: MarketKind = "outcome" if market_kind == "outcome" else "perp"
    handle = instrument_handle(
        venue="hyperliquid", symbol=instrument_key, market_kind=kind
    )
    stamp = created_at or datetime.now(UTC)
    envelope = OpportunityEnvelope(
        envelope_id=f"hl:{family}:{handle}:{side}",
        venue="paper",
        target_venue="hyperliquid",
        market_kind=kind,
        side=side,
        size_band=size_band,
        urgency=urgency(edge_score),
        edge_score=float(edge_score),
        ttl_seconds=int(ttl_seconds),
        invalidation=invalidation,
        instrument_handle=handle,
        status="open",
        created_at=stamp,
    )
    sealed = SealedInstrument(
        handle=handle,
        venue="hyperliquid",
        symbol=instrument_key.upper(),
        market_kind=kind,
        family=family,
    )
    return envelope, sealed


def assert_clerk_payload_is_blind(
    payload: dict[str, Any],
    *,
    banned_symbols: tuple[str, ...] = (),
) -> None:
    """Raise AssertionError if a clerk payload leaked desk fields or tickers."""
    lowered_keys = {str(key).lower() for key in payload}
    leaked = lowered_keys & {
        "symbol",
        "factors",
        "notes",
        "thesis",
        "setup_type",
        "fingerprint",
        "optimistic_entry",
        "honest_entry",
        "mark_price",
    }
    if leaked:
        raise AssertionError(f"clerk payload leaked desk fields: {sorted(leaked)}")
    blob = " ".join(f"{k}={v}" for k, v in payload.items()).upper()
    for symbol in banned_symbols:
        token = symbol.upper()
        if not token:
            continue
        if re.search(rf"(?<![A-Z0-9]){re.escape(token)}(?![A-Z0-9])", blob):
            raise AssertionError(f"clerk payload leaked symbol {token}")
