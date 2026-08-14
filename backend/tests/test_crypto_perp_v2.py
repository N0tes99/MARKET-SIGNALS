"""Crypto perps paper v2 — momentum + Bybit + F&G + Reddit cache."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pandas as pd

from app.engines.paper_agent.agent import PaperAgent, _fingerprint
from app.engines.paper_agent.crypto_perp_v2 import (
    SETUP_TYPE,
    _OHLCV_LIMIT,
    scan_crypto_perp_v2,
    score_symbol,
)
from app.engines.paper_agent.store import PaperTradeStore
from app.engines.paper_agent.types import PaperTrade
from app.market_data.providers.bybit_derivatives import DerivativesDepth


class _EmptyFeed:
    def scan_feed(self, **_kwargs):
        return []


class _Market:
    def __init__(self, mom_pct: float = 4.0) -> None:
        self._mom_pct = mom_pct

    def get_ticker(self, symbol):
        return SimpleNamespace(price=100.0)

    def safe_get_ohlcv(self, symbol, timeframe, limit=96):
        # Build 1h bars so 12h momentum ≈ mom_pct
        n = max(limit, 20)
        start = 100.0
        end = start * (1.0 + self._mom_pct / 100.0)
        rows = []
        for i in range(n):
            t = i / max(n - 1, 1)
            close = start + (end - start) * t
            rows.append(
                {
                    "timestamp": datetime(2026, 8, 13, 0, 0, tzinfo=UTC),
                    "open": close,
                    "high": close * 1.01,
                    "low": close * 0.99,
                    "close": close,
                    "volume": 10.0,
                }
            )
        return pd.DataFrame(rows)


def _depth(*, funding: float = -0.0004, oi_hist: list[float] | None = None) -> DerivativesDepth:
    return DerivativesDepth(
        symbol="BTC",
        funding_rate=funding,
        open_interest=1_000_000.0,
        mark_price=100.0,
        funding_history=[funding] * 8,
        oi_history=oi_hist or [100.0, 98.0],
        source="bybit",
    )


def test_momentum_ohlcv_limit_meets_safe_get_min_rows() -> None:
    # MarketDataService.safe_get_ohlcv validates min_rows=20 — requesting fewer
    # silently yields no momentum and a dead scanner.
    assert _OHLCV_LIMIT >= 20


def test_score_symbol_long_with_supporting_funding(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.crypto_perp_v2.fetch_derivatives_depth",
        lambda symbol, timeout=2.0: _depth(funding=-0.0005),
    )
    monkeypatch.setattr(
        "app.engines.paper_agent.crypto_perp_v2.fetch_fear_greed",
        lambda: (35, "Fear"),
    )
    monkeypatch.setattr(
        "app.engines.paper_agent.crypto_perp_v2.analyze_reddit_social",
        lambda symbol, allow_live=False: SimpleNamespace(
            available=False, lean=0.0, description="", score=50.0
        ),
    )
    idea = score_symbol(_Market(4.0), "BTC")  # type: ignore[arg-type]
    assert idea is not None
    assert idea.direction == "long"
    assert idea.setup_type == SETUP_TYPE
    assert idea.confidence >= 55.0
    assert any("momentum" in f.lower() for f in idea.factors)


def test_score_symbol_skips_flat_momentum(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.crypto_perp_v2.fetch_derivatives_depth",
        lambda symbol, timeout=2.0: _depth(),
    )
    monkeypatch.setattr(
        "app.engines.paper_agent.crypto_perp_v2.fetch_fear_greed",
        lambda: (50, "Neutral"),
    )
    monkeypatch.setattr(
        "app.engines.paper_agent.crypto_perp_v2.analyze_reddit_social",
        lambda symbol, allow_live=False: SimpleNamespace(
            available=False, lean=0.0, description="", score=50.0
        ),
    )
    assert score_symbol(_Market(0.2), "ETH") is None  # type: ignore[arg-type]


def test_scan_crypto_perp_v2_orders_by_confidence(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.crypto_perp_v2.fetch_derivatives_depth",
        lambda symbol, timeout=2.0: _depth(funding=-0.0004),
    )
    monkeypatch.setattr(
        "app.engines.paper_agent.crypto_perp_v2.fetch_fear_greed",
        lambda: (40, "Fear"),
    )
    monkeypatch.setattr(
        "app.engines.paper_agent.crypto_perp_v2.analyze_reddit_social",
        lambda symbol, allow_live=False: SimpleNamespace(
            available=False, lean=0.0, description="", score=50.0
        ),
    )
    ideas = scan_crypto_perp_v2(_Market(5.0), symbols=("BTC", "ETH"))  # type: ignore[arg-type]
    assert len(ideas) == 2
    assert ideas[0].confidence >= ideas[1].confidence


def _agent(store=None, market=None):
    return PaperAgent(
        market_data=market or _Market(5.0),  # type: ignore[arg-type]
        crypto_scanner=_EmptyFeed(),  # type: ignore[arg-type]
        equity_scanner=_EmptyFeed(),  # type: ignore[arg-type]
        tape_scanner=None,
        store=store or PaperTradeStore(),
        pipeline=None,
        size_usd=2500.0,
    )


def test_agent_opens_crypto_perp_v2(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_crypto_perp_v2",
        lambda market, min_confidence=55.0: [
            SimpleNamespace(
                symbol="BTC",
                direction="long",
                setup_type=SETUP_TYPE,
                confidence=72.0,
                factors=["12h momentum +5.0%"],
            )
        ],
    )
    agent = _agent()
    notes = agent.tick()
    assert any(n.startswith("open:BTC:perp_momentum") for n in notes)
    trades = agent.store.list_all()
    assert len(trades) == 1
    assert trades[0].source == "crypto_perp_v2"
    assert trades[0].setup_type == SETUP_TYPE
    assert _fingerprint("crypto_perp_v2", "BTC", SETUP_TYPE, "long") == trades[0].fingerprint


def test_agent_crypto_perp_v2_sub_cap(monkeypatch) -> None:
    store = PaperTradeStore()
    now = datetime.now(UTC)
    for i, sym in enumerate(("BTC", "ETH")):
        store.upsert(
            PaperTrade(
                id=f"t{i}",
                symbol=sym,
                source="crypto_perp_v2",
                setup_type=SETUP_TYPE,
                direction="long",
                fingerprint=_fingerprint("crypto_perp_v2", sym, SETUP_TYPE, "long"),
                signal_at=now,
                confidence=70.0,
                opportunity_score=70.0,
                size_usd=2500.0,
                status="open",
                optimistic_entry=100.0,
                optimistic_entry_at=now,
            )
        )

    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_crypto_perp_v2",
        lambda market, min_confidence=55.0: [
            SimpleNamespace(
                symbol="SOL",
                direction="long",
                setup_type=SETUP_TYPE,
                confidence=80.0,
                factors=["12h momentum +6.0%"],
            )
        ],
    )
    agent = _agent(store=store)
    notes = agent.tick()
    assert any(n.startswith("skip:crypto_perp_v2_cap:SOL") for n in notes)
    assert not any(n.startswith("open:SOL:") for n in notes)


def test_layer2_crypto_still_opens_alongside_v2(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_crypto_perp_v2",
        lambda market, min_confidence=55.0: [],
    )

    class _Crypto:
        def scan_feed(self, **_kwargs):
            return [
                SimpleNamespace(
                    symbol="LINK",
                    setup_type="funding_extreme",
                    direction_bias="short",
                    confidence=68.0,
                    factors=["Funding +9 bps"],
                )
            ]

    agent = PaperAgent(
        market_data=_Market(0.0),  # type: ignore[arg-type]
        crypto_scanner=_Crypto(),  # type: ignore[arg-type]
        equity_scanner=_EmptyFeed(),  # type: ignore[arg-type]
        store=PaperTradeStore(),
        pipeline=None,
        size_usd=2500.0,
    )
    notes = agent.tick()
    assert any(n.startswith("open:LINK:funding_extreme") for n in notes)
    assert agent.store.list_all()[0].source == "crypto_setup"
