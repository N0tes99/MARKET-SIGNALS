"""Hot Tape hunts can open paper under the same confirm + daily cap."""

from datetime import UTC, datetime
from types import SimpleNamespace

from app.engines.paper_agent.agent import PaperAgent, _fingerprint
from app.engines.paper_agent.store import PaperTradeStore


class _EmptyFeed:
    def scan_feed(self, **_kwargs):
        return []


class _Tape:
    def __init__(self, hunts):
        self.hunts = hunts
        self.calls = 0

    def scan_board(self, **_kwargs):
        self.calls += 1
        longs = [h for h in self.hunts if h.direction == "long"]
        shorts = [h for h in self.hunts if h.direction == "short"]
        return SimpleNamespace(longs=longs, shorts=shorts)


class _Market:
    def get_ticker(self, symbol):
        return SimpleNamespace(price=100.5)

    def safe_get_ohlcv(self, symbol, timeframe, limit=96):
        ts = datetime(2026, 8, 12, 14, 0, tzinfo=UTC)
        import pandas as pd

        return pd.DataFrame(
            [
                {
                    "timestamp": ts,
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.5,
                    "volume": 10.0,
                }
            ]
        )


def _hot(symbol="NVDA", direction="long", heat="hot", score=78.0):
    return SimpleNamespace(
        symbol=symbol,
        direction=direction,
        heat=heat,
        hunt_score=score,
        relative_volume=2.4,
        factors=["rel vol standout"],
    )


def _agent(tape, pipeline=None, store=None):
    return PaperAgent(
        market_data=_Market(),  # type: ignore[arg-type]
        crypto_scanner=_EmptyFeed(),  # type: ignore[arg-type]
        equity_scanner=_EmptyFeed(),  # type: ignore[arg-type]
        tape_scanner=tape,
        store=store or PaperTradeStore(),
        pipeline=pipeline,
        size_usd=2500.0,
    )


def test_tape_hot_fingerprint_and_note(monkeypatch) -> None:
    monkeypatch.setattr("app.engines.paper_agent.agent.us_cash_session_open", lambda _now: True)
    tape = _Tape([_hot()])
    agent = _agent(tape)
    notes = agent.tick()
    assert any(n.startswith("open:NVDA:tape_hunt") for n in notes)
    trades = agent.store.list_all()
    assert len(trades) == 1
    t = trades[0]
    assert t.source == "tape_hunt"
    assert t.fingerprint == _fingerprint("tape_hunt", "NVDA", "tape_hunt", "long")
    assert "tape hunt 78" in t.notes
    assert "rel vol 2.40x" in t.notes


def test_tape_warm_ignored(monkeypatch) -> None:
    monkeypatch.setattr("app.engines.paper_agent.agent.us_cash_session_open", lambda _now: True)
    tape = _Tape([_hot(heat="warm", score=80.0)])
    agent = _agent(tape)
    agent.tick()
    assert agent.store.list_all() == []


def test_tape_confirm_still_required(monkeypatch) -> None:
    monkeypatch.setattr("app.engines.paper_agent.agent.us_cash_session_open", lambda _now: True)
    monkeypatch.setattr("app.engines.paper_agent.confirm.earnings_soon", lambda *_a, **_k: False)

    class _Pipe:
        def evaluate(self, symbol, timeframe="1h"):
            return SimpleNamespace(
                opportunity=SimpleNamespace(trade_grade="C"),
                risk=SimpleNamespace(
                    score=30.0,
                    risk_reward_ratio=0.8,
                    stop_loss=90.0,
                    take_profit=110.0,
                ),
            )

    tape = _Tape([_hot()])
    agent = _agent(tape, pipeline=_Pipe())
    notes = agent.tick()
    assert any("skip:" in n and "NVDA" in n for n in notes)
    assert agent.store.list_all() == []


def test_tape_weekend_skipped(monkeypatch) -> None:
    monkeypatch.setattr("app.engines.paper_agent.agent.us_cash_session_open", lambda _now: False)
    tape = _Tape([_hot()])
    agent = _agent(tape)
    agent.tick()
    assert agent.store.list_all() == []
    assert tape.calls == 0


def test_tape_daily_cap_shared(monkeypatch) -> None:
    monkeypatch.setattr("app.engines.paper_agent.agent.us_cash_session_open", lambda _now: True)
    store = PaperTradeStore()
    tape = _Tape(
        [
            _hot("NVDA"),
            _hot("AAPL"),
            _hot("MSFT"),
            _hot("AMD"),
        ]
    )
    agent = _agent(tape, store=store)
    agent.tick()
    assert len(store.list_all()) == 4
    assert all(t.source == "tape_hunt" for t in store.list_all())
