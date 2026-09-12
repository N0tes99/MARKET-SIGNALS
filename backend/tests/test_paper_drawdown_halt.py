"""Drawdown halt freezes new paper opens until the book recovers."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd

from app.engines.paper_agent.agent import PaperAgent
from app.engines.paper_agent.crypto_perp_v2 import SETUP_TYPE
from app.engines.paper_agent.paper_policy import (
    DRAWDOWN_HALT_META_KEY,
    new_opens_halted_from_returns,
)
from app.engines.paper_agent.store import PaperTradeStore
from app.engines.paper_agent.types import PaperTrade


class _Feed:
    def scan_feed(self, *args, **kwargs):
        return []


class _Market:
    def get_ticker(self, symbol):
        if symbol in {"ETH", "SOL", "XRP", "LOSS"}:
            return SimpleNamespace(price=100.0)
        return SimpleNamespace(price=65000.0)

    def safe_get_ohlcv(self, symbol, timeframe, limit=96):
        ts = datetime(2026, 9, 11, 15, 0, tzinfo=UTC)
        return pd.DataFrame(
            [
                {
                    "timestamp": ts,
                    "open": 64900.0,
                    "high": 65000.0,
                    "low": 64800.0,
                    "close": 64950.0,
                    "volume": 10.0,
                }
            ]
        )


def _closed_loss(*, pnl: float, now: datetime) -> PaperTrade:
    return PaperTrade(
        id=str(uuid4()),
        symbol="LOSS",
        source="crypto_perp_v2",
        setup_type="perp_momentum",
        direction="long",
        fingerprint=f"loss-{pnl}",
        signal_at=now - timedelta(days=1),
        confidence=70.0,
        opportunity_score=70.0,
        size_usd=2500.0,
        status="closed",
        optimistic_entry=100.0,
        optimistic_entry_at=now - timedelta(days=1),
        optimistic_exit=96.0,
        optimistic_pnl_usd=pnl,
        optimistic_return_pct=(pnl / 2500.0) * 100.0,
        honest_entry=100.0,
        honest_entry_at=now - timedelta(days=1),
        honest_exit=96.0,
        honest_pnl_usd=pnl,
        honest_return_pct=(pnl / 2500.0) * 100.0,
        closed_at=now - timedelta(hours=2),
        close_reason="stop_loss_-3.0%",
    )


def _open_btc(now: datetime) -> PaperTrade:
    return PaperTrade(
        id=str(uuid4()),
        symbol="ETH",
        source="crypto_perp_v2",
        setup_type="perp_momentum",
        direction="long",
        fingerprint="eth-open",
        signal_at=now - timedelta(hours=2),
        confidence=70.0,
        opportunity_score=70.0,
        size_usd=2500.0,
        status="open",
        optimistic_entry=100.0,
        optimistic_entry_at=now - timedelta(hours=2),
        honest_entry=100.0,
        honest_entry_at=now - timedelta(hours=2),
        mark_price=100.0,
    )


def _agent(store: PaperTradeStore, monkeypatch, now: datetime) -> PaperAgent:
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

    class _DT:
        @staticmethod
        def now(tz=None):
            return now

    monkeypatch.setattr("app.engines.paper_agent.agent.datetime", _DT)
    return PaperAgent(
        market_data=_Market(),  # type: ignore[arg-type]
        crypto_scanner=_Feed(),  # type: ignore[arg-type]
        equity_scanner=_Feed(),  # type: ignore[arg-type]
        store=store,
        size_usd=2500.0,
    )


def test_hysteresis_trips_at_five_and_holds_until_minus_two() -> None:
    assert new_opens_halted_from_returns(
        optimistic_return_pct=-5.0,
        honest_return_pct=-4.0,
        currently_halted=False,
    )
    assert new_opens_halted_from_returns(
        optimistic_return_pct=-4.9,
        honest_return_pct=-4.0,
        currently_halted=False,
    ) is False
    assert new_opens_halted_from_returns(
        optimistic_return_pct=-3.0,
        honest_return_pct=-3.0,
        currently_halted=True,
    )
    assert new_opens_halted_from_returns(
        optimistic_return_pct=-2.0,
        honest_return_pct=-1.5,
        currently_halted=True,
    ) is False


def test_drawdown_halt_blocks_new_opens_and_still_manages(monkeypatch) -> None:
    now = datetime(2026, 9, 11, 15, 0, tzinfo=UTC)
    store = PaperTradeStore()
    store.upsert(_closed_loss(pnl=-800.0, now=now))
    store.upsert(_open_btc(now))
    agent = _agent(store, monkeypatch, now)

    notes = agent.tick()
    assert "skip:drawdown_halt" in notes
    assert not any(n.startswith("open:BTC") for n in notes)
    assert store.get_meta(DRAWDOWN_HALT_META_KEY) == "1"
    summary = agent.summary()
    assert summary.drawdown_halted is True
    assert summary.max_concurrent_opens == 3
    # Existing ETH still marked/managed (not flattened by the halt).
    eth = next(t for t in store.list_all() if t.symbol == "ETH")
    assert eth.status in {"open", "pending_honest", "closing", "closed"}
    assert eth.mark_price is not None


def test_drawdown_halt_clears_after_recovery(monkeypatch) -> None:
    now = datetime(2026, 9, 11, 15, 0, tzinfo=UTC)
    store = PaperTradeStore()
    store.set_meta(DRAWDOWN_HALT_META_KEY, "1")
    store.upsert(_closed_loss(pnl=-100.0, now=now))
    agent = _agent(store, monkeypatch, now)

    notes = agent.tick()
    assert "skip:drawdown_halt" not in notes
    assert any(n.startswith("open:BTC:perp_momentum") for n in notes)
    assert store.get_meta(DRAWDOWN_HALT_META_KEY) == "0"


def test_paused_cme_squeeze_tape_do_not_scan(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.paper_policy.PAUSED_NEW_OPEN_SOURCES",
        frozenset(
            {
                "equity_setup",
                "crypto_setup",
                "cme_futures",
                "squeeze_expansion",
                "tape_hunt",
            }
        ),
    )
    cme_calls = {"n": 0}
    squeeze_calls = {"n": 0}

    def _cme(*_a, **_k):
        cme_calls["n"] += 1
        return []

    def _squeeze(*_a, **_k):
        squeeze_calls["n"] += 1
        return []

    monkeypatch.setattr("app.engines.paper_agent.agent.scan_cme_paper_ideas", _cme)
    monkeypatch.setattr("app.engines.paper_agent.agent.scan_squeeze_expansion", _squeeze)
    monkeypatch.setattr("app.engines.paper_agent.agent.scan_crypto_perp_v2", lambda *a, **k: [])

    class _Tape:
        def scan_board(self, **_kwargs):
            raise AssertionError("paused tape must not scan")

    now = datetime(2026, 9, 11, 15, 0, tzinfo=UTC)

    class _DT:
        @staticmethod
        def now(tz=None):
            return now

    monkeypatch.setattr("app.engines.paper_agent.agent.datetime", _DT)
    agent = PaperAgent(
        market_data=_Market(),  # type: ignore[arg-type]
        crypto_scanner=_Feed(),  # type: ignore[arg-type]
        equity_scanner=_Feed(),  # type: ignore[arg-type]
        tape_scanner=_Tape(),
        store=PaperTradeStore(),
        size_usd=2500.0,
        cortex=SimpleNamespace(last_memory=None),
    )
    notes = agent.tick()
    assert "skip:paused:cme_futures" in notes
    assert "skip:paused:squeeze_expansion" in notes
    assert "skip:paused:tape_hunt" in notes
    assert cme_calls["n"] == 0
    assert squeeze_calls["n"] == 0
    assert agent.store.list_all() == []


def test_concurrent_cap_stops_at_three(monkeypatch) -> None:
    now = datetime(2026, 9, 11, 15, 0, tzinfo=UTC)
    store = PaperTradeStore()
    for symbol in ("ETH", "SOL", "XRP"):
        store.upsert(
            PaperTrade(
                id=str(uuid4()),
                symbol=symbol,
                source="crypto_perp_v2",
                setup_type="perp_momentum",
                direction="long",
                fingerprint=f"{symbol}-open",
                signal_at=now - timedelta(hours=1),
                confidence=70.0,
                opportunity_score=70.0,
                size_usd=2500.0,
                status="open",
                optimistic_entry=100.0,
                optimistic_entry_at=now - timedelta(hours=1),
                honest_entry=100.0,
                honest_entry_at=now - timedelta(hours=1),
                mark_price=100.0,
            )
        )
    agent = _agent(store, monkeypatch, now)
    notes = agent.tick()
    assert any(n.startswith("skip:max_open:3") for n in notes)
    assert not any(n.startswith("open:BTC") for n in notes)
    assert len(store.open_or_pending()) == 3
