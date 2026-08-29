"""Paused paper factories do not open new trades (CSV 2026-08-29 sleeve cut)."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pandas as pd

from app.engines.paper_agent.agent import PaperAgent
from app.engines.paper_agent.store import PaperTradeStore


def test_paused_sources_do_not_open(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.paper_policy.PAUSED_NEW_OPEN_SOURCES",
        frozenset({"equity_setup", "crypto_setup"}),
    )
    store = PaperTradeStore()
    weekday = datetime(2026, 8, 10, 15, 0, tzinfo=UTC)  # Monday ET-friendly

    crypto_calls = {"n": 0}
    equity_calls = {"n": 0}

    class _Crypto:
        def scan_feed(self, *args, **kwargs):
            crypto_calls["n"] += 1
            return [
                SimpleNamespace(
                    symbol="BTC",
                    setup_type="funding_extreme",
                    direction_bias="short",
                    confidence=70.0,
                    factors=["funding elevated"],
                )
            ]

    class _Equity:
        def scan_feed(self, *args, **kwargs):
            equity_calls["n"] += 1
            return [
                SimpleNamespace(
                    symbol="AAPL",
                    setup_type="momentum_continuation",
                    direction_bias="long",
                    confidence=70.0,
                    opportunity_score=70.0,
                    factors=["momentum"],
                )
            ]

    class _Market:
        def get_ticker(self, symbol):
            return SimpleNamespace(price=100.0)

        def safe_get_ohlcv(self, symbol, timeframe, limit=96):
            return pd.DataFrame(
                [
                    {
                        "timestamp": weekday + timedelta(minutes=15),
                        "open": 100.0,
                        "high": 101.0,
                        "low": 99.0,
                        "close": 100.5,
                        "volume": 10.0,
                    }
                ]
            )

    agent = PaperAgent(
        market_data=_Market(),  # type: ignore[arg-type]
        crypto_scanner=_Crypto(),  # type: ignore[arg-type]
        equity_scanner=_Equity(),  # type: ignore[arg-type]
        store=store,
        size_usd=2500.0,
    )

    class _DT:
        @staticmethod
        def now(tz=None):
            return weekday

    monkeypatch.setattr("app.engines.paper_agent.agent.datetime", _DT)
    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_crypto_perp_v2",
        lambda *a, **k: [],
    )

    notes = agent.tick()
    assert "skip:paused:crypto_setup" in notes
    assert "skip:paused:equity_setup" in notes
    assert not any(n.startswith("open:") for n in notes)
    assert store.list_all() == []
    assert crypto_calls["n"] == 0
    assert equity_calls["n"] == 0
    summary = agent.summary()
    assert summary.paused_new_opens == ["crypto_setup", "equity_setup"]


def _pause(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.paper_policy.PAUSED_NEW_OPEN_SOURCES",
        frozenset({"equity_setup", "crypto_setup"}),
    )


def test_paused_sources_still_manage_existing_opens(monkeypatch) -> None:
    """SMCI-style leftovers keep SL/TP; pause is new-opens only."""
    from uuid import uuid4

    from app.engines.paper_agent.types import PaperTrade

    _pause(monkeypatch)
    store = PaperTradeStore()
    opened = datetime(2026, 8, 9, 15, 0, tzinfo=UTC)
    store.upsert(
        PaperTrade(
            id=str(uuid4()),
            symbol="SMCI",
            source="equity_setup",
            setup_type="momentum_continuation",
            direction="long",
            fingerprint="smci-fp",
            signal_at=opened,
            confidence=70.0,
            opportunity_score=70.0,
            size_usd=2500.0,
            status="open",
            optimistic_entry=100.0,
            optimistic_entry_at=opened,
            honest_entry=100.0,
            honest_entry_at=opened,
            mark_price=100.0,
        )
    )

    class _Market:
        def get_ticker(self, symbol):
            return SimpleNamespace(price=109.0)

        def safe_get_ohlcv(self, symbol, timeframe, limit=96):
            return pd.DataFrame()

    class _Feed:
        def scan_feed(self, *args, **kwargs):
            raise AssertionError("paused factory must not scan")

    agent = PaperAgent(
        market_data=_Market(),  # type: ignore[arg-type]
        crypto_scanner=_Feed(),  # type: ignore[arg-type]
        equity_scanner=_Feed(),  # type: ignore[arg-type]
        store=store,
        size_usd=2500.0,
    )
    agent._last_discover_at = opened

    notes = agent.tick()
    assert any(n.startswith("opt_close:SMCI") for n in notes)
    remaining = store.list_all()
    assert remaining
    assert remaining[0].optimistic_exit is not None
    assert remaining[0].close_reason


def test_perp_v2_still_opens_while_losers_paused(monkeypatch) -> None:
    from app.engines.paper_agent.crypto_perp_v2 import SETUP_TYPE

    _pause(monkeypatch)
    store = PaperTradeStore()
    weekday = datetime(2026, 8, 10, 15, 0, tzinfo=UTC)

    class _Feed:
        def scan_feed(self, *args, **kwargs):
            raise AssertionError("paused factory must not scan")

    class _Market:
        def get_ticker(self, symbol):
            return SimpleNamespace(price=65000.0)

        def safe_get_ohlcv(self, symbol, timeframe, limit=96):
            return pd.DataFrame(
                [
                    {
                        "timestamp": weekday + timedelta(minutes=15),
                        "open": 64900.0,
                        "high": 65000.0,
                        "low": 64800.0,
                        "close": 64950.0,
                        "volume": 10.0,
                    }
                ]
            )

    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_crypto_perp_v2",
        lambda *a, **k: [
            SimpleNamespace(
                symbol="BTC",
                direction="long",
                setup_type=SETUP_TYPE,
                confidence=72.0,
                factors=["12h momentum +5.0%"],
                extras={"funding_bps": 1.0},
            )
        ],
    )

    agent = PaperAgent(
        market_data=_Market(),  # type: ignore[arg-type]
        crypto_scanner=_Feed(),  # type: ignore[arg-type]
        equity_scanner=_Feed(),  # type: ignore[arg-type]
        store=store,
        size_usd=2500.0,
    )

    class _DT:
        @staticmethod
        def now(tz=None):
            return weekday

    monkeypatch.setattr("app.engines.paper_agent.agent.datetime", _DT)

    notes = agent.tick()
    assert "skip:paused:crypto_setup" in notes
    assert "skip:paused:equity_setup" in notes
    assert any(n.startswith("open:BTC:perp_momentum") for n in notes)
    trades = store.list_all()
    assert len(trades) == 1
    assert trades[0].source == "crypto_perp_v2"
