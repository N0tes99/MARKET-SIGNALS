"""Paper agent dual-ledger unit tests."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pandas as pd

from app.engines.paper_agent.agent import PaperAgent
from app.engines.paper_agent.broker import next_bar_open_after, should_close, unrealized_pnl
from app.engines.paper_agent.store import PaperTradeStore


def test_unrealized_long_short() -> None:
    pnl, ret = unrealized_pnl(direction="long", entry=100.0, mark=110.0, size_usd=1000.0)
    assert ret == 10.0
    assert pnl == 100.0
    pnl_s, ret_s = unrealized_pnl(direction="short", entry=100.0, mark=90.0, size_usd=1000.0)
    assert ret_s == 10.0
    assert pnl_s == 100.0


def test_should_close_tp_sl() -> None:
    now = datetime.now(UTC)
    assert should_close(
        direction="long",
        entry=100.0,
        mark=106.5,
        opened_at=now,
        now=now,
    ) is not None
    assert should_close(
        direction="long",
        entry=100.0,
        mark=96.5,
        opened_at=now,
        now=now,
    ) is not None
    assert (
        should_close(
            direction="long",
            entry=100.0,
            mark=101.0,
            opened_at=now,
            now=now,
        )
        is None
    )


def test_next_bar_open_after() -> None:
    signal = datetime(2026, 8, 9, 14, 0, tzinfo=UTC)
    rows = []
    for i in range(5):
        rows.append(
            {
                "timestamp": signal + timedelta(minutes=15 * (i - 1)),
                "open": 100.0 + i,
                "high": 101.0 + i,
                "low": 99.0 + i,
                "close": 100.5 + i,
                "volume": 1000.0,
            }
        )
    frame = pd.DataFrame(rows)

    class _M:
        def safe_get_ohlcv(self, symbol, timeframe, limit=96):
            return frame

    out = next_bar_open_after(_M(), "SPY", signal)  # type: ignore[arg-type]
    assert out is not None
    open_px, bar_ts = out
    assert open_px == 102.0
    assert bar_ts > signal


def test_paper_store_clear_all() -> None:
    store = PaperTradeStore()
    from uuid import uuid4

    from app.engines.paper_agent.types import PaperTrade

    now = datetime.now(UTC)
    store.upsert(
        PaperTrade(
            id=str(uuid4()),
            symbol="BTC",
            source="crypto_setup",
            setup_type="funding_extreme",
            direction="long",
            fingerprint="abc",
            signal_at=now,
            confidence=60.0,
            opportunity_score=60.0,
            size_usd=2500.0,
            status="open",
            optimistic_entry=100.0,
            optimistic_entry_at=now,
        )
    )
    store.set_meta("last_tick_at", now.isoformat())
    assert len(store.list_all()) == 1
    assert store.clear_all() == 1
    assert store.list_all() == []
    assert store.get_meta("last_tick_at") is None


def test_agent_opens_from_watch_ideas(monkeypatch) -> None:
    store = PaperTradeStore()
    signal_at = datetime(2026, 8, 9, 15, 0, tzinfo=UTC)

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

    class _Equity:
        def scan_feed(self, *args, **kwargs):
            return []

    class _Market:
        def get_ticker(self, symbol):
            return SimpleNamespace(price=65000.0)

        def safe_get_ohlcv(self, symbol, timeframe, limit=96):
            return pd.DataFrame(
                [
                    {
                        "timestamp": signal_at + timedelta(minutes=15),
                        "open": 64900.0,
                        "high": 65000.0,
                        "low": 64800.0,
                        "close": 64950.0,
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
            return signal_at

    monkeypatch.setattr("app.engines.paper_agent.agent.datetime", _DT)

    notes = agent.tick()
    assert any(n.startswith("open:BTC") for n in notes)
    trades = store.list_all()
    assert len(trades) == 1
    t = trades[0]
    assert t.optimistic_entry > 0
    assert t.honest_entry is not None
    assert t.honest_bar_ts is not None
    assert t.fingerprint
    assert store.get_meta("last_tick_at") == signal_at.isoformat()

    summary = agent.summary()
    assert summary.optimistic.open_positions == 1
    assert summary.honest.open_positions == 1
    assert summary.starting_cash == 15_000.0

    cleared = agent.reset()
    assert cleared == 1
    reset_summary = agent.summary()
    assert reset_summary.optimistic.equity == 15_000.0
    assert reset_summary.honest.equity == 15_000.0
    assert reset_summary.optimistic.closed_trades == 0
    assert reset_summary.honest.closed_trades == 0
    assert reset_summary.open_trades == []
    assert reset_summary.recent_closed == []
    assert reset_summary.last_tick_at is None


def test_memory_store_roundtrip_meta() -> None:
    store = PaperTradeStore()
    store.set_meta("last_tick_at", "2026-08-09T15:00:00+00:00")
    assert store.get_meta("last_tick_at") == "2026-08-09T15:00:00+00:00"


def test_opt_close_appears_in_history(monkeypatch, caplog) -> None:
    """Optimistic exit must show in recent_closed (status closing) while honest still open."""
    import logging

    store = PaperTradeStore()
    from uuid import uuid4

    from app.engines.paper_agent.types import PaperTrade

    opened = datetime(2026, 8, 9, 15, 0, tzinfo=UTC)
    trade = PaperTrade(
        id=str(uuid4()),
        symbol="ETH",
        source="crypto_setup",
        setup_type="funding_extreme",
        direction="long",
        fingerprint="eth-fp",
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
    store.upsert(trade)

    class _Crypto:
        def scan_feed(self, *args, **kwargs):
            return []

    class _Equity:
        def scan_feed(self, *args, **kwargs):
            return []

    # Price hits take-profit (~8%+) so should_close fires for opt; honest same entry also exits.
    # Use a mark that closes opt but we want honest still open — should_close is shared so both
    # would fire on same mark. Force honest to stay by temporarily making opened_at recent for
    # honest via a huge entry distance that only opt sees... Actually both use same should_close.
    # So both legs close on TP together → status closed, still in recent_closed.
    # Better test: mark hits TP, both exit, assert recent_closed + logging.
    # Separate test for closing-only: mock should_close to return reason only once for opt.

    class _Market:
        def get_ticker(self, symbol):
            return SimpleNamespace(price=109.0)

        def safe_get_ohlcv(self, symbol, timeframe, limit=96):
            return pd.DataFrame()

    agent = PaperAgent(
        market_data=_Market(),  # type: ignore[arg-type]
        crypto_scanner=_Crypto(),  # type: ignore[arg-type]
        equity_scanner=_Equity(),  # type: ignore[arg-type]
        store=store,
        size_usd=2500.0,
    )
    # Skip discovery path noise — last_discover set so discover skipped
    agent._last_discover_at = opened

    calls = {"n": 0}

    def _fake_should_close(*, direction, entry, mark, opened_at, now, **kwargs):
        # First call is optimistic; second would be honest — only close opt first tick.
        calls["n"] += 1
        if calls["n"] == 1:
            return "take_profit"
        return None

    monkeypatch.setattr("app.engines.paper_agent.agent.should_close", _fake_should_close)

    with caplog.at_level(logging.INFO, logger="app.engines.paper_agent.agent"):
        notes = agent.tick()

    assert any(n.startswith("opt_close:ETH") for n in notes)
    assert any(n.startswith("paper_closing:ETH") for n in notes)
    summary = agent.summary()
    assert summary.optimistic.closed_trades == 1
    assert summary.honest.closed_trades == 0
    assert summary.honest.open_positions == 1
    assert summary.open_trades == []
    assert len(summary.recent_closed) == 1
    assert summary.recent_closed[0].status == "closing"
    assert summary.recent_closed[0].close_reason == "take_profit"
    assert "paper_opt_close" in caplog.text
    assert "paper_closing" in caplog.text

    # Second tick: honest hits TP → fully closed, still in history
    def _fake_should_close_honest(*, direction, entry, mark, opened_at, now, **kwargs):
        return "take_profit"

    monkeypatch.setattr("app.engines.paper_agent.agent.should_close", _fake_should_close_honest)
    with caplog.at_level(logging.INFO, logger="app.engines.paper_agent.agent"):
        notes2 = agent.tick()
    assert any(n.startswith("honest_close:ETH") for n in notes2)
    assert any(n.startswith("paper_close:ETH") for n in notes2)
    summary2 = agent.summary()
    assert summary2.recent_closed[0].status == "closed"
    assert summary2.optimistic.closed_trades == 1
    assert summary2.honest.closed_trades == 1
    assert "paper_close" in caplog.text


def test_discover_skipped_between_interval(monkeypatch) -> None:
    store = PaperTradeStore()
    t0 = datetime(2026, 8, 9, 15, 0, tzinfo=UTC)
    scans = {"crypto": 0}

    class _Crypto:
        def scan_feed(self, *args, **kwargs):
            scans["crypto"] += 1
            return []

    class _Equity:
        def scan_feed(self, *args, **kwargs):
            return []

    class _Market:
        def get_ticker(self, symbol):
            return SimpleNamespace(price=1.0)

        def safe_get_ohlcv(self, symbol, timeframe, limit=96):
            return pd.DataFrame()

    agent = PaperAgent(
        market_data=_Market(),  # type: ignore[arg-type]
        crypto_scanner=_Crypto(),  # type: ignore[arg-type]
        equity_scanner=_Equity(),  # type: ignore[arg-type]
        store=store,
    )

    class _DT:
        now_val = t0

        @classmethod
        def now(cls, tz=None):
            return cls.now_val

    monkeypatch.setattr("app.engines.paper_agent.agent.datetime", _DT)
    notes1 = agent.tick()
    assert "discover:skipped" not in notes1
    assert scans["crypto"] == 1

    _DT.now_val = t0 + timedelta(seconds=30)
    notes2 = agent.tick()
    assert "discover:skipped" in notes2
    assert scans["crypto"] == 1


def test_daily_open_cap_picks_best(monkeypatch) -> None:
    """Up to 5 opens/day — ranks by score and stops at the daily budget."""
    store = PaperTradeStore()
    signal_at = datetime(2026, 8, 9, 15, 0, tzinfo=UTC)

    ideas = [
        SimpleNamespace(
            symbol="AAA",
            setup_type="funding_extreme",
            direction_bias="long",
            confidence=51.0,
            factors=["low"],
        ),
        SimpleNamespace(
            symbol="BBB",
            setup_type="funding_extreme",
            direction_bias="short",
            confidence=80.0,
            factors=["best"],
        ),
        SimpleNamespace(
            symbol="CCC",
            setup_type="funding_extreme",
            direction_bias="long",
            confidence=70.0,
            factors=["mid"],
        ),
        SimpleNamespace(
            symbol="DDD",
            setup_type="funding_extreme",
            direction_bias="short",
            confidence=65.0,
            factors=["also"],
        ),
        SimpleNamespace(
            symbol="EEE",
            setup_type="funding_extreme",
            direction_bias="long",
            confidence=60.0,
            factors=["also2"],
        ),
        SimpleNamespace(
            symbol="FFF",
            setup_type="funding_extreme",
            direction_bias="short",
            confidence=58.0,
            factors=["also3"],
        ),
        SimpleNamespace(
            symbol="GGG",
            setup_type="funding_extreme",
            direction_bias="long",
            confidence=56.0,
            factors=["cut"],
        ),
    ]

    class _Crypto:
        def scan_feed(self, *args, **kwargs):
            return ideas

    class _Equity:
        def scan_feed(self, *args, **kwargs):
            return []

    class _Market:
        def get_ticker(self, symbol):
            return SimpleNamespace(price=100.0)

        def safe_get_ohlcv(self, symbol, timeframe, limit=96):
            return pd.DataFrame(
                [
                    {
                        "timestamp": signal_at + timedelta(minutes=15),
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
            return signal_at

    monkeypatch.setattr("app.engines.paper_agent.agent.datetime", _DT)
    notes = agent.tick()
    opens = [n for n in notes if n.startswith("open:")]
    assert len(opens) == 5
    assert any("BBB" in n for n in opens)
    assert any("CCC" in n for n in opens)
    assert any("DDD" in n for n in opens)
    assert any("EEE" in n for n in opens)
    assert any("FFF" in n for n in opens)
    assert not any("AAA" in n for n in opens)
    assert not any("GGG" in n for n in opens)
    assert "skip:daily_cap:5" in notes

    # Same UTC day — no more opens even if discover forced
    agent._last_discover_at = None
    notes2 = agent.tick()
    assert not any(n.startswith("open:") for n in notes2)
    assert "skip:daily_cap:5" in notes2


def test_paper_feeds_learning_memory_and_maturity(monkeypatch) -> None:
    from uuid import uuid4

    from app.engines.learning_engine import LearningEngine
    from app.engines.learning_engine.store import InMemorySignalStore
    from app.engines.paper_agent.types import PaperTrade

    learning = LearningEngine(store=InMemorySignalStore())
    store = PaperTradeStore()
    signal_at = datetime(2026, 8, 9, 15, 0, tzinfo=UTC)

    class _Crypto:
        def scan_feed(self, *args, **kwargs):
            return [
                SimpleNamespace(
                    symbol="SOL",
                    setup_type="funding_extreme",
                    direction_bias="long",
                    confidence=72.0,
                    factors=["crowd"],
                )
            ]

    class _Equity:
        def scan_feed(self, *args, **kwargs):
            return []

    class _Market:
        def get_ticker(self, symbol):
            return SimpleNamespace(price=100.0)

        def safe_get_ohlcv(self, symbol, timeframe, limit=96):
            return pd.DataFrame(
                [
                    {
                        "timestamp": signal_at + timedelta(minutes=15),
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
        learning=learning,
        size_usd=2500.0,
    )

    class _DT:
        @staticmethod
        def now(tz=None):
            return signal_at

    monkeypatch.setattr("app.engines.paper_agent.agent.datetime", _DT)
    agent.tick()
    opened = store.list_all()[0]
    assert opened.signal_record_id
    mem = learning.list_paper_memory()
    assert len(mem) == 1
    assert mem[0].source == "paper_honest"
    assert mem[0].outcome is None

    # Force closed with honest PnL → memory outcome
    opened.status = "closed"
    opened.closed_at = signal_at + timedelta(hours=2)
    opened.honest_exit = 106.0
    opened.honest_return_pct = 6.0
    opened.honest_pnl_usd = 150.0
    opened.close_reason = "take_profit_+6%"
    store.upsert(opened)
    agent._remember_close(opened)
    mem2 = learning.list_paper_memory()
    assert mem2[0].outcome == "win"
    assert mem2[0].realized_return_pct == 6.0

    # Seed enough synthetic honest closes for maturity progress
    for i in range(29):
        store.upsert(
            PaperTrade(
                id=str(uuid4()),
                symbol=f"X{i}",
                source="crypto_setup",
                setup_type="funding_extreme",
                direction="long",
                fingerprint=f"fp{i}",
                signal_at=signal_at,
                confidence=60.0,
                opportunity_score=60.0,
                size_usd=2500.0,
                status="closed",
                optimistic_entry=100.0,
                optimistic_entry_at=signal_at,
                optimistic_exit=106.0,
                optimistic_pnl_usd=150.0,
                optimistic_return_pct=6.0,
                honest_entry=100.0,
                honest_entry_at=signal_at,
                honest_exit=106.0,
                honest_pnl_usd=150.0,
                honest_return_pct=6.0,
                closed_at=signal_at + timedelta(hours=i + 1),
                close_reason="take_profit_+6%",
            )
        )
        # Memory outcomes lagged — only one real memory row unless we mirror
        learning.record_paper_open(
            paper_trade_id=str(uuid4()),
            symbol=f"X{i}",
            setup_type="funding_extreme",
            direction="long",
            confidence=60.0,
            opportunity_score=60.0,
            entry_price=100.0,
        )

    # Resolve extra memory rows to approach target
    for rec in learning.list_paper_memory(limit=500):
        if rec.outcome is None and rec.paper_trade_id is not None:
            learning.resolve_paper_close(
                paper_trade_id=rec.paper_trade_id,
                outcome="win",
                realized_return_pct=6.0,
                close_reason="seed",
            )

    mat = agent.maturity()
    assert mat.honest_closed >= 30
    assert mat.memory_outcomes >= 20
    assert mat.expectancy_ok
    assert mat.drawdown_ok
    assert mat.ready_for_private_live
    summary = agent.summary()
    assert summary.maturity is not None
    assert summary.maturity.score_pct >= 99.0


def test_ledger_single_closed_loss_is_negative() -> None:
    """One finished loser must drive red totals — closed P&L equals total when flat."""
    store = PaperTradeStore()
    from uuid import uuid4

    from app.engines.paper_agent.types import PaperTrade

    opened = datetime(2026, 8, 9, 15, 0, tzinfo=UTC)
    store.upsert(
        PaperTrade(
            id=str(uuid4()),
            symbol="BTC",
            source="crypto_setup",
            setup_type="funding_extreme",
            direction="long",
            fingerprint="btc-loss",
            signal_at=opened,
            confidence=70.0,
            opportunity_score=70.0,
            size_usd=2500.0,
            status="closed",
            optimistic_entry=100.0,
            optimistic_entry_at=opened,
            optimistic_exit=97.0,
            optimistic_pnl_usd=-75.0,
            optimistic_return_pct=-3.0,
            honest_entry=100.0,
            honest_entry_at=opened,
            honest_exit=97.0,
            honest_pnl_usd=-75.0,
            honest_return_pct=-3.0,
            closed_at=opened + timedelta(hours=2),
            close_reason="stop_loss_-3%",
            mark_price=110.0,  # recovered after exit — must not affect closed ledger
        )
    )

    class _Crypto:
        def scan_feed(self, *args, **kwargs):
            return []

    class _Equity:
        def scan_feed(self, *args, **kwargs):
            return []

    class _Market:
        def get_ticker(self, symbol):
            return SimpleNamespace(price=110.0)

        def safe_get_ohlcv(self, symbol, timeframe, limit=96):
            return pd.DataFrame()

    agent = PaperAgent(
        market_data=_Market(),  # type: ignore[arg-type]
        crypto_scanner=_Crypto(),  # type: ignore[arg-type]
        equity_scanner=_Equity(),  # type: ignore[arg-type]
        store=store,
        size_usd=2500.0,
        starting_cash=15_000.0,
    )
    summary = agent.summary()
    assert summary.optimistic.closed_trades == 1
    assert summary.optimistic.wins == 0
    assert summary.optimistic.losses == 1
    assert summary.optimistic.realized_pnl == -75.0
    assert summary.optimistic.unrealized_pnl == 0.0
    assert summary.optimistic.total_pnl == -75.0
    assert summary.optimistic.equity == 14_925.0
    assert summary.honest.total_pnl == -75.0
    assert summary.honest.losses == 1


def test_ledger_exit_without_pnl_uses_exit_not_live_mark() -> None:
    """Partial rows with exit but missing pnl must not MTM at a recovered mark."""
    store = PaperTradeStore()
    from uuid import uuid4

    from app.engines.paper_agent.types import PaperTrade

    opened = datetime(2026, 8, 9, 15, 0, tzinfo=UTC)
    store.upsert(
        PaperTrade(
            id=str(uuid4()),
            symbol="ETH",
            source="crypto_setup",
            setup_type="funding_extreme",
            direction="long",
            fingerprint="eth-partial",
            signal_at=opened,
            confidence=70.0,
            opportunity_score=70.0,
            size_usd=2500.0,
            status="closed",
            optimistic_entry=100.0,
            optimistic_entry_at=opened,
            optimistic_exit=97.0,
            optimistic_pnl_usd=None,
            optimistic_return_pct=None,
            honest_entry=None,
            closed_at=opened + timedelta(hours=1),
            close_reason="stop_loss_-3%",
            mark_price=108.0,
        )
    )

    class _Crypto:
        def scan_feed(self, *args, **kwargs):
            return []

    class _Equity:
        def scan_feed(self, *args, **kwargs):
            return []

    class _Market:
        def get_ticker(self, symbol):
            return SimpleNamespace(price=108.0)

        def safe_get_ohlcv(self, symbol, timeframe, limit=96):
            return pd.DataFrame()

    agent = PaperAgent(
        market_data=_Market(),  # type: ignore[arg-type]
        crypto_scanner=_Crypto(),  # type: ignore[arg-type]
        equity_scanner=_Equity(),  # type: ignore[arg-type]
        store=store,
        size_usd=2500.0,
        starting_cash=15_000.0,
    )
    opt = agent.summary().optimistic
    assert opt.closed_trades == 1
    assert opt.losses == 1
    assert opt.total_pnl < 0
    assert abs(opt.realized_pnl - (-75.0)) < 0.01


def test_should_close_uses_trade_atr_levels() -> None:
    now = datetime.now(UTC)
    assert (
        should_close(
            direction="long",
            entry=100.0,
            mark=103.0,
            opened_at=now,
            now=now,
            take_profit_pct=8.0,
            stop_loss_pct=4.0,
        )
        is None
    )
    assert should_close(
        direction="long",
        entry=100.0,
        mark=108.2,
        opened_at=now,
        now=now,
        take_profit_pct=8.0,
        stop_loss_pct=4.0,
    ) == "take_profit_+8.0%"
    assert should_close(
        direction="short",
        entry=100.0,
        mark=95.5,
        opened_at=now,
        now=now,
        take_profit_pct=4.5,
        stop_loss_pct=2.2,
    ) == "take_profit_+4.5%"


def test_watch_bar_skips_ignore_band(monkeypatch) -> None:
    store = PaperTradeStore()
    signal_at = datetime(2026, 8, 10, 15, 0, tzinfo=UTC)  # Monday

    class _Crypto:
        def scan_feed(self, *args, **kwargs):
            return [
                SimpleNamespace(
                    symbol="BTC",
                    setup_type="funding_extreme",
                    direction_bias="long",
                    confidence=54.9,
                    factors=["ignore-band"],
                )
            ]

    class _Equity:
        def scan_feed(self, *args, **kwargs):
            return []

    class _Market:
        def get_ticker(self, symbol):
            return SimpleNamespace(price=65000.0)

        def safe_get_ohlcv(self, symbol, timeframe, limit=96):
            return pd.DataFrame()

    agent = PaperAgent(
        market_data=_Market(),  # type: ignore[arg-type]
        crypto_scanner=_Crypto(),  # type: ignore[arg-type]
        equity_scanner=_Equity(),  # type: ignore[arg-type]
        store=store,
    )

    class _DT:
        @staticmethod
        def now(tz=None):
            return signal_at

    monkeypatch.setattr("app.engines.paper_agent.agent.datetime", _DT)
    notes = agent.tick()
    assert not any(n.startswith("open:") for n in notes)
    assert store.list_all() == []


def test_weekend_skips_us_cash_equity(monkeypatch) -> None:
    from app.engines.paper_agent.agent import us_cash_session_open

    sunday = datetime(2026, 8, 9, 15, 0, tzinfo=UTC)
    monday = datetime(2026, 8, 10, 15, 0, tzinfo=UTC)
    assert us_cash_session_open(sunday) is False
    assert us_cash_session_open(monday) is True

    store = PaperTradeStore()
    scanned = {"n": 0}

    class _Crypto:
        def scan_feed(self, *args, **kwargs):
            return []

    class _Equity:
        def scan_feed(self, *args, **kwargs):
            scanned["n"] += 1
            return [
                SimpleNamespace(
                    symbol="NVDA",
                    setup_type="daily_momentum",
                    direction_bias="long",
                    confidence=80.0,
                    factors=["yahoo friday last"],
                )
            ]

    class _Market:
        def get_ticker(self, symbol):
            return SimpleNamespace(price=180.0)

        def safe_get_ohlcv(self, symbol, timeframe, limit=96):
            return pd.DataFrame()

    agent = PaperAgent(
        market_data=_Market(),  # type: ignore[arg-type]
        crypto_scanner=_Crypto(),  # type: ignore[arg-type]
        equity_scanner=_Equity(),  # type: ignore[arg-type]
        store=store,
    )

    class _DT:
        @staticmethod
        def now(tz=None):
            return sunday

    monkeypatch.setattr("app.engines.paper_agent.agent.datetime", _DT)
    notes = agent.tick()
    assert "skip:equity_weekend" in notes
    assert scanned["n"] == 0
    assert store.list_all() == []
