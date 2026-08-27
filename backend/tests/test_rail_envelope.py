"""Rail envelopes must never leak symbol, thesis, or prices to the clerk."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.engines.paper_agent.types import PaperTrade
from app.engines.rail.envelope import (
    assert_clerk_payload_is_blind,
    instrument_handle,
    mint_from_paper_trade,
    size_band,
    urgency,
)


def _trade(**overrides: object) -> PaperTrade:
    now = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
    payload: dict[str, object] = {
        "id": str(uuid4()),
        "symbol": "BTC",
        "source": "crypto_perp_v2",
        "setup_type": "perp_momentum",
        "direction": "long",
        "fingerprint": "secret-fingerprint",
        "signal_at": now,
        "confidence": 72.0,
        "opportunity_score": 81.0,
        "size_usd": 2500.0,
        "status": "open",
        "optimistic_entry": 64000.0,
        "optimistic_entry_at": now,
        "factors": ["funding crowded", "12h momentum"],
        "notes": "do not leak this thesis",
        "stop_loss_pct": 3.0,
    }
    payload.update(overrides)
    return PaperTrade(**payload)  # type: ignore[arg-type]


def test_size_and_urgency_bands() -> None:
    assert size_band(500) == "xs"
    assert size_band(1200) == "s"
    assert size_band(2500) == "m"
    assert size_band(4000) == "l"
    assert urgency(55) == "passive"
    assert urgency(66) == "normal"
    assert urgency(80) == "aggressive"


def test_equity_and_cme_never_enter_crypto_rails() -> None:
    assert mint_from_paper_trade(_trade(source="equity_setup", symbol="SPY")) is None
    assert mint_from_paper_trade(_trade(source="cme_futures", symbol="ES=F")) is None
    assert mint_from_paper_trade(_trade(source="tape_hunt", symbol="NVDA")) is None


def test_clerk_payload_is_blind() -> None:
    pair = mint_from_paper_trade(_trade())
    assert pair is not None
    envelope, sealed = pair
    payload = envelope.clerk_dict()
    assert_clerk_payload_is_blind(payload, banned_symbols=("BTC", "SPY", "SOL"))
    blob = json.dumps(payload)
    assert "BTC" not in blob
    assert "funding crowded" not in blob
    assert "perp_momentum" not in blob
    assert "64000" not in blob
    assert "secret-fingerprint" not in blob
    assert payload["venue"] == "paper"
    assert payload["target_venue"] == "hyperliquid"
    assert payload["side"] == "buy"
    assert payload["size_band"] == "m"
    assert payload["invalidation"] == "stop_band_3"
    assert sealed.symbol == "BTC"
    assert sealed.handle == envelope.instrument_handle
    assert sealed.handle == instrument_handle(
        venue="hyperliquid", symbol="BTC", market_kind="perp"
    )


def test_short_squeeze_maps_to_sell() -> None:
    pair = mint_from_paper_trade(
        _trade(source="squeeze_expansion", direction="short", confidence=58.0)
    )
    assert pair is not None
    envelope, _sealed = pair
    assert envelope.side == "sell"
    assert envelope.urgency == "passive"
    assert envelope.market_kind == "perp"


def test_assert_clerk_payload_catches_symbol_leak() -> None:
    with pytest.raises(AssertionError, match="leaked symbol BTC"):
        assert_clerk_payload_is_blind({"note": "buy BTC"}, banned_symbols=("BTC",))


def test_assert_clerk_payload_does_not_flag_hyperliquid_as_hype() -> None:
    assert_clerk_payload_is_blind(
        {"target_venue": "hyperliquid", "invalidation": "hl_funding"},
        banned_symbols=("HYPE", "BTC", "SOL"),
    )
