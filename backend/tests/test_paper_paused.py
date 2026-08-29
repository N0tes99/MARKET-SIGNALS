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
