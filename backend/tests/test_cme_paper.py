"""Paper CME futures — discover, daily cap, F&G bypass, learning isolation."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd
import pytest

from app.engines.learning_engine import LearningEngine, SignalOutcome
from app.engines.learning_engine.store import InMemorySignalStore
from app.engines.paper_agent.agent import PaperAgent, _fingerprint
from app.engines.paper_agent.cme_momentum import (
    SETUP_TYPE,
    SOURCE,
    idea_from_row,
    scan_cme_paper_ideas,
)
from app.engines.paper_agent.confirm import confirm_open
from app.engines.paper_agent.store import PaperTradeStore
from app.engines.paper_agent.types import PaperTrade
from app.engines.runner_engine.cme_futures import CmeFuturesRow
from app.engines.runner_engine.crypto_learn import (
    encode_paper_open_notes,
    get_crypto_learn_coefficients,
    get_crypto_learn_config,
    maybe_retune_from_paper,
    parse_paper_notes,
)


class _EmptyFeed:
    def scan_feed(self, **_kwargs):
        return []


class _Market:
    def __init__(self, last: float = 5400.0) -> None:
        self._last = last

    def get_ticker(self, symbol):
        return SimpleNamespace(price=self._last)

    def safe_get_ohlcv(self, symbol, timeframe, limit=96):
        n = max(limit, 20)
        rows = []
        for i in range(n):
            close = self._last * (1.0 + i * 0.0002)
            rows.append(
                {
                    "timestamp": datetime(2026, 8, 17, 0, 0, tzinfo=UTC),
                    "open": close,
                    "high": close * 1.004,
                    "low": close * 0.996,
                    "close": close,
                    "volume": 10_000.0,
                }
            )
        return pd.DataFrame(rows)


def _row(
    *,
    symbol: str = "ES=F",
    bucket: str = "trending",
    score: float = 72.0,
    last: float | None = 5400.0,
    mom_12h: float | None = 2.5,
    change_pct: float | None = 0.8,
    oi: float | None = 1_200_000.0,
    cot_index: float | None = None,
    cot_spec_net: float | None = None,
    cot_effect: str | None = None,
) -> CmeFuturesRow:
    return CmeFuturesRow(
        id=f"cme-futures:{symbol}",
        symbol=symbol,
        name="E-mini S&P 500",
        group="index",
        bucket=bucket,  # type: ignore[arg-type]
        score=score,
        last=last,
        change_pct=change_pct,
        open_interest=oi,
        mom_12h_pct=mom_12h,
        factors=["12h +2.5%"],
        cot_index=cot_index,
        cot_spec_net=cot_spec_net,
        cot_effect=cot_effect,  # type: ignore[arg-type]
    )


def _idea(symbol: str = "ES=F", direction: str = "long", score: float = 72.0):
    mom = 2.5 if direction == "long" else -2.5
    idea = idea_from_row(_row(symbol=symbol, score=score, mom_12h=mom))
    assert idea is not None
    return idea


def _agent(store=None, market=None, pipeline=None, learning=None):
    return PaperAgent(
        market_data=market or _Market(),  # type: ignore[arg-type]
        crypto_scanner=_EmptyFeed(),  # type: ignore[arg-type]
        equity_scanner=_EmptyFeed(),  # type: ignore[arg-type]
        tape_scanner=None,
        store=store or PaperTradeStore(),
        pipeline=pipeline,
        learning=learning,
        size_usd=2500.0,
    )


def test_idea_from_row_long_trending() -> None:
    idea = idea_from_row(_row())
    assert idea is not None
    assert idea.symbol == "ES=F"
    assert idea.direction == "long"
    assert idea.setup_type == SETUP_TYPE
    assert idea.confidence >= 55.0
    assert idea.extras["group"] == "index"
    assert idea.extras["bucket"] == "trending"
    assert idea.extras["oi"] == 1_200_000.0


def test_idea_from_row_skips_quiet_and_missing_last() -> None:
    assert idea_from_row(_row(bucket="quiet", score=70.0)) is None
    assert idea_from_row(_row(last=None)) is None
    assert idea_from_row(_row(score=50.0)) is None


def test_idea_from_row_uses_change_pct_when_mom_missing() -> None:
    idea = idea_from_row(_row(mom_12h=None, change_pct=-1.2, bucket="extended", score=58.0))
    assert idea is not None
    assert idea.direction == "short"


def test_idea_from_row_skips_crowded_cot() -> None:
    assert idea_from_row(_row(cot_index=90.0, mom_12h=2.5)) is None
    assert idea_from_row(_row(cot_index=10.0, mom_12h=-2.5)) is None
    idea = idea_from_row(_row(cot_index=10.0, mom_12h=2.5, cot_effect="strengthen", cot_spec_net=-200_000))
    assert idea is not None
    assert idea.extras["cot_index"] == pytest.approx(10.0)
    assert idea.extras["cot_effect"] == "strengthen"
    assert idea.extras["cot_spec_net"] == pytest.approx(-200_000)


def test_scan_cme_paper_ideas_filters(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.cme_momentum.scan_cme_futures",
        lambda market: [
            _row(symbol="ES=F", bucket="trending", score=70.0),
            _row(symbol="CL=F", bucket="quiet", score=80.0, last=70.0),
            _row(symbol="GC=F", bucket="extended", score=60.0, last=None),
        ],
    )
    ideas = scan_cme_paper_ideas(_Market())  # type: ignore[arg-type]
    assert [i.symbol for i in ideas] == ["ES=F"]


def test_agent_opens_mocked_es(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_cme_paper_ideas",
        lambda market, min_confidence=55.0: [_idea()],
    )
    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_crypto_perp_v2",
        lambda market, min_confidence=55.0: [],
    )
    learning = LearningEngine(store=InMemorySignalStore())
    agent = _agent(learning=learning)
    notes = agent.tick()
    assert any(n.startswith("open:ES=F:cme_momentum") for n in notes)
    trades = agent.store.list_all()
    assert len(trades) == 1
    assert trades[0].source == SOURCE
    assert trades[0].setup_type == SETUP_TYPE
    assert trades[0].direction == "long"
    assert _fingerprint(SOURCE, "ES=F", SETUP_TYPE, "long") == trades[0].fingerprint
    mem = learning.list_paper_memory()
    assert len(mem) == 1
    parsed = parse_paper_notes(mem[0].notes)
    assert parsed["setup"] == SETUP_TYPE
    assert parsed["group"] == "index"
    assert parsed["bucket"] == "trending"
    assert parsed["score"] == pytest.approx(72.0)
    assert parsed["mom_12h_pct"] == pytest.approx(2.5)
    assert parsed["change_pct"] == pytest.approx(0.8)
    assert parsed["oi"] == pytest.approx(1_200_000.0)
    assert learning.outcome_stats_by_setup("cme_momentum")["open"] == 1


def test_agent_cme_daily_cap(monkeypatch) -> None:
    store = PaperTradeStore()
    now = datetime.now(UTC)
    for i, sym in enumerate(("NQ=F", "YM=F", "RTY=F")):
        store.upsert(
            PaperTrade(
                id=f"t{i}",
                symbol=sym,
                source=SOURCE,
                setup_type=SETUP_TYPE,
                direction="long",
                fingerprint=_fingerprint(SOURCE, sym, SETUP_TYPE, "long"),
                signal_at=now,
                confidence=70.0,
                opportunity_score=70.0,
                size_usd=2500.0,
                status="open",
                optimistic_entry=18000.0,
                optimistic_entry_at=now,
            )
        )
    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_cme_paper_ideas",
        lambda market, min_confidence=55.0: [_idea("ES=F")],
    )
    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_crypto_perp_v2",
        lambda market, min_confidence=55.0: [],
    )
    notes = _agent(store=store).tick()
    assert any(n.startswith("skip:cme_futures_cap:ES=F") for n in notes)
    assert not any(n.startswith("open:ES=F:") for n in notes)


def test_agent_cme_respects_global_daily_cap(monkeypatch) -> None:
    store = PaperTradeStore()
    now = datetime.now(UTC)
    for i, sym in enumerate(("BTC", "ETH", "SOL", "AVAX", "LINK")):
        store.upsert(
            PaperTrade(
                id=f"c{i}",
                symbol=sym,
                source="crypto_setup",
                setup_type="funding_extreme",
                direction="long",
                fingerprint=_fingerprint("crypto_setup", sym, "funding_extreme", "long"),
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
        "app.engines.paper_agent.agent.scan_cme_paper_ideas",
        lambda market, min_confidence=55.0: [_idea("ES=F")],
    )
    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_crypto_perp_v2",
        lambda market, min_confidence=55.0: [],
    )
    notes = _agent(store=store).tick()
    assert any(n.startswith("skip:daily_cap:") for n in notes)
    assert not any(n.startswith("open:ES=F:") for n in notes)


class _ExplodingPipe:
    def evaluate(self, symbol, timeframe="1h"):
        raise AssertionError(f"pipeline should not evaluate {symbol}")


def test_confirm_cme_not_blocked_by_fng(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.confirm.fetch_fear_greed",
        lambda: (82, "Extreme Greed"),
    )
    skip, tp, sl, note = confirm_open(
        symbol="ES=F",
        direction="long",
        pipeline=_ExplodingPipe(),
        entry_price=5400.0,
        source="cme_futures",
        market=None,
    )
    assert skip is None
    assert tp == 6.0
    assert sl == 3.0
    assert "cme" in note


def test_confirm_es_f_without_source_skips_pipeline(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.confirm.fetch_fear_greed",
        lambda: (12, "Extreme Fear"),
    )
    skip, _, _, note = confirm_open(
        symbol="ES=F",
        direction="short",
        pipeline=_ExplodingPipe(),
        entry_price=5400.0,
    )
    assert skip is None
    assert "cme" in note


def test_confirm_cme_uses_yahoo_atr(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.confirm.fetch_fear_greed",
        lambda: (82, "Extreme Greed"),
    )
    skip, tp, sl, note = confirm_open(
        symbol="ES=F",
        direction="long",
        pipeline=_ExplodingPipe(),
        entry_price=5400.0,
        source="cme_futures",
        market=_Market(),
    )
    assert skip is None
    assert sl >= 0.4
    assert tp >= sl
    assert "ATR" in note


def test_agent_opens_cme_with_exploding_pipeline(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_cme_paper_ideas",
        lambda market, min_confidence=55.0: [_idea()],
    )
    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_crypto_perp_v2",
        lambda market, min_confidence=55.0: [],
    )
    monkeypatch.setattr(
        "app.engines.paper_agent.confirm.fetch_fear_greed",
        lambda: (82, "Extreme Greed"),
    )
    notes = _agent(pipeline=_ExplodingPipe()).tick()
    assert any(n.startswith("open:ES=F:cme_momentum") for n in notes)


def test_cme_stats_do_not_retune_crypto_learn() -> None:
    get_crypto_learn_config().reset(persist=False)
    notes = encode_paper_open_notes(
        setup_type=SETUP_TYPE,
        direction="long",
        extras={
            "group": "index",
            "bucket": "trending",
            "score": 72.0,
            "mom_12h_pct": 2.5,
            "change_pct": 0.8,
            "oi": 1_200_000.0,
            "cot_index": 18.0,
            "cot_spec_net": -280_446.0,
            "cot_effect": "strengthen",
            "cot_report_date": "2026-08-11",
        },
    )
    parsed = parse_paper_notes(notes)
    assert parsed["setup"] == SETUP_TYPE
    assert parsed["group"] == "index"
    assert parsed["oi"] == pytest.approx(1_200_000.0)
    assert parsed["cot_index"] == pytest.approx(18.0)
    assert parsed["cot_effect"] == "strengthen"

    engine = LearningEngine(store=InMemorySignalStore())
    for _ in range(12):
        engine.record_paper_open(
            paper_trade_id=uuid4(),
            symbol="ES=F",
            setup_type=SETUP_TYPE,
            direction="long",
            confidence=70.0,
            opportunity_score=70.0,
            entry_price=5400.0,
            extras={
                "group": "index",
                "bucket": "trending",
                "score": 72.0,
                "mom_12h_pct": 2.5,
                "change_pct": 0.8,
                "oi": 1_200_000.0,
            },
        )
    for rec in engine.list_paper_memory(limit=500):
        if rec.paper_trade_id is not None:
            engine.resolve_paper_close(
                paper_trade_id=rec.paper_trade_id,
                outcome=SignalOutcome.WIN.value,
                realized_return_pct=2.0,
            )

    cme = engine.outcome_stats_by_setup("cme_momentum")
    perp = engine.outcome_stats_by_setup("perp_momentum")
    assert cme["resolved"] == 12
    assert cme["win_rate"] == 100.0
    assert perp["resolved"] == 0
    assert maybe_retune_from_paper(engine) is None
    assert get_crypto_learn_coefficients().preset == "default"
