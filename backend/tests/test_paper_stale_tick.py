"""Stale paper ticks manage leftover opens and do not open into a gap."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd

from app.engines.paper_agent.agent import PaperAgent
from app.engines.paper_agent.broker import MAX_HOLD_HOURS
from app.engines.paper_agent.paper_policy import (
    STALE_TICK_SECONDS,
    last_tick_age_seconds,
    paper_tick_stale,
)
from app.engines.paper_agent.store import PaperTradeStore
from app.engines.paper_agent.types import PaperTrade


class _Feed:
    def scan_feed(self, *args, **kwargs):
        raise AssertionError("stale tick must not scan idea factories")


class _Priced:
    def __init__(self, price: float | None) -> None:
        self.price = price

    def get_ticker(self, symbol):
        if self.price is None:
            return None
        return SimpleNamespace(price=self.price)

    def safe_get_ohlcv(self, symbol, timeframe, limit=96):
        return pd.DataFrame()


def _open_trade(
    *,
    symbol: str = "SMCI",
    source: str = "equity_setup",
    opened: datetime,
    mark: float | None = 100.0,
    entry: float = 100.0,
) -> PaperTrade:
    return PaperTrade(
        id=str(uuid4()),
        symbol=symbol,
        source=source,  # type: ignore[arg-type]
        setup_type="momentum_continuation",
        direction="long",
        fingerprint=f"{symbol}-stale",
        signal_at=opened,
        confidence=70.0,
        opportunity_score=70.0,
        size_usd=2500.0,
        status="open",
        optimistic_entry=entry,
        optimistic_entry_at=opened,
        honest_entry=entry,
        honest_entry_at=opened,
        mark_price=mark,
    )


def test_paper_tick_stale_helper() -> None:
    now = datetime(2026, 8, 29, 22, 0, tzinfo=UTC)
    assert paper_tick_stale(None, now) is False
    fresh = now - timedelta(seconds=STALE_TICK_SECONDS - 30)
    assert paper_tick_stale(fresh, now) is False
    dead = now - timedelta(seconds=STALE_TICK_SECONDS)
    assert paper_tick_stale(dead, now) is True
    assert last_tick_age_seconds(dead, now) == float(STALE_TICK_SECONDS)


def test_stale_tick_skips_discover_and_closes_max_hold(monkeypatch) -> None:
    now = datetime.now(UTC)
    opened = now - timedelta(hours=MAX_HOLD_HOURS + 8)
    store = PaperTradeStore()
    store.set_meta("last_tick_at", (now - timedelta(hours=6)).isoformat())
    store.upsert(_open_trade(opened=opened, mark=100.2))

    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_crypto_perp_v2",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no v2 scan")),
    )

    agent = PaperAgent(
        market_data=_Priced(100.2),  # type: ignore[arg-type]
        crypto_scanner=_Feed(),  # type: ignore[arg-type]
        equity_scanner=_Feed(),  # type: ignore[arg-type]
        store=store,
        size_usd=2500.0,
    )
    notes = agent.tick()
    assert "skip:stale_tick" in notes
    assert not any(n.startswith("open:") for n in notes)
    assert any(n.startswith("opt_close:SMCI:stale:max_hold_") for n in notes)
    closed = store.list_all()[0]
    assert closed.status == "closed"
    assert closed.close_reason and closed.close_reason.startswith("stale:max_hold_")


def test_stale_tick_labels_missed_stop(monkeypatch) -> None:
    now = datetime.now(UTC)
    opened = now - timedelta(hours=10)
    store = PaperTradeStore()
    store.set_meta("last_tick_at", (now - timedelta(hours=6)).isoformat())
    store.upsert(_open_trade(symbol="WIF", source="crypto_setup", opened=opened, mark=100.0))

    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_crypto_perp_v2",
        lambda *a, **k: [],
    )

    agent = PaperAgent(
        market_data=_Priced(96.4),  # type: ignore[arg-type]
        crypto_scanner=_Feed(),  # type: ignore[arg-type]
        equity_scanner=_Feed(),  # type: ignore[arg-type]
        store=store,
        size_usd=2500.0,
    )
    notes = agent.tick()
    assert "skip:stale_tick" in notes
    assert any("stale:stop_loss" in n for n in notes)
    assert store.list_all()[0].close_reason and store.list_all()[0].close_reason.startswith(
        "stale:stop_loss"
    )


def test_stale_mark_flattens_past_max_hold() -> None:
    now = datetime.now(UTC)
    opened = now - timedelta(hours=MAX_HOLD_HOURS + 4)
    store = PaperTradeStore()
    store.set_meta("last_tick_at", (now - timedelta(hours=8)).isoformat())
    store.upsert(_open_trade(opened=opened, mark=None))

    agent = PaperAgent(
        market_data=_Priced(None),  # type: ignore[arg-type]
        crypto_scanner=_Feed(),  # type: ignore[arg-type]
        equity_scanner=_Feed(),  # type: ignore[arg-type]
        store=store,
        size_usd=2500.0,
    )
    notes = agent.tick()
    assert "stale_mark:SMCI" in notes
    trade = store.list_all()[0]
    assert trade.status == "closed"
    assert trade.close_reason and trade.close_reason.startswith("stale:")
    assert trade.optimistic_pnl_usd is not None


def test_second_tick_after_stale_discovers(monkeypatch) -> None:
    """Keep-warm after a sleep: first tick catchup-only, second tick may open."""
    now = datetime.now(UTC)
    store = PaperTradeStore()
    store.set_meta("last_tick_at", (now - timedelta(hours=3)).isoformat())

    idea = SimpleNamespace(
        symbol="BTC",
        setup_type="perp_momentum",
        direction="long",
        confidence=72.0,
        factors=["12h momentum"],
        extras={"funding_bps": 1.0},
    )

    class _Silent:
        def scan_feed(self, *args, **kwargs):
            return []

    class _Market:
        def get_ticker(self, symbol):
            return SimpleNamespace(price=65000.0)

        def safe_get_ohlcv(self, symbol, timeframe, limit=96):
            return pd.DataFrame(
                [
                    {
                        "timestamp": now + timedelta(minutes=15),
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
        lambda *a, **k: [idea],
    )

    agent = PaperAgent(
        market_data=_Market(),  # type: ignore[arg-type]
        crypto_scanner=_Silent(),  # type: ignore[arg-type]
        equity_scanner=_Silent(),  # type: ignore[arg-type]
        store=store,
        size_usd=2500.0,
    )
    first = agent.tick()
    assert "skip:stale_tick" in first
    assert not any(n.startswith("open:") for n in first)

    from app.api.routes.paper import _tick_agent

    store.set_meta("last_tick_at", (now - timedelta(hours=3)).isoformat())
    agent._last_tick_at = now - timedelta(hours=3)
    notes = _tick_agent(agent)
    assert "skip:stale_tick" in notes
    assert "discover_after_catchup" in notes
    assert any(n.startswith("open:BTC") for n in notes)


def test_fresh_tick_still_discovers(monkeypatch) -> None:
    now = datetime.now(UTC)
    store = PaperTradeStore()
    store.set_meta("last_tick_at", (now - timedelta(seconds=30)).isoformat())

    idea = SimpleNamespace(
        symbol="BTC",
        setup_type="funding_extreme",
        direction_bias="short",
        confidence=70.0,
        factors=["funding elevated"],
    )

    class _Crypto:
        def scan_feed(self, *args, **kwargs):
            return [idea]

    class _Empty:
        def scan_feed(self, *args, **kwargs):
            return []

    class _Market:
        def get_ticker(self, symbol):
            return SimpleNamespace(price=65000.0)

        def safe_get_ohlcv(self, symbol, timeframe, limit=96):
            return pd.DataFrame(
                [
                    {
                        "timestamp": now + timedelta(minutes=15),
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
        lambda *a, **k: [],
    )

    agent = PaperAgent(
        market_data=_Market(),  # type: ignore[arg-type]
        crypto_scanner=_Crypto(),  # type: ignore[arg-type]
        equity_scanner=_Empty(),  # type: ignore[arg-type]
        store=store,
        size_usd=2500.0,
    )
    notes = agent.tick()
    assert "skip:stale_tick" not in notes
    assert any(n.startswith("open:BTC") for n in notes)


def test_summary_reports_tick_stale_before_catchup() -> None:
    now = datetime.now(UTC)
    store = PaperTradeStore()
    store.set_meta("last_tick_at", (now - timedelta(hours=6)).isoformat())
    store.upsert(_open_trade(opened=now - timedelta(hours=10)))
    agent = PaperAgent(
        market_data=_Priced(100.0),  # type: ignore[arg-type]
        crypto_scanner=_Feed(),  # type: ignore[arg-type]
        equity_scanner=_Feed(),  # type: ignore[arg-type]
        store=store,
        size_usd=2500.0,
    )
    summary = agent.summary()
    assert summary.tick_stale is True
    assert summary.last_tick_age_seconds is not None
    assert summary.last_tick_age_seconds >= 6 * 3600 - 5
