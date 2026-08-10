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
        mark=109.0,
        opened_at=now,
        now=now,
    ) is not None
    assert should_close(
        direction="long",
        entry=100.0,
        mark=95.5,
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


def test_memory_store_roundtrip_meta() -> None:
    store = PaperTradeStore()
    store.set_meta("last_tick_at", "2026-08-09T15:00:00+00:00")
    assert store.get_meta("last_tick_at") == "2026-08-09T15:00:00+00:00"
