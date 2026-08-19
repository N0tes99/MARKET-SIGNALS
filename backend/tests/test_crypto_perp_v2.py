"""Crypto perps paper v2 — momentum + Bybit + F&G + Reddit cache."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from app.engines.paper_agent.agent import PaperAgent, _fingerprint
from app.engines.paper_agent.crypto_perp_v2 import (
    _OHLCV_LIMIT,
    SETUP_TYPE,
    V2_UNIVERSE,
    scan_crypto_perp_v2,
    score_symbol,
)
from app.engines.paper_agent.store import PaperTradeStore
from app.engines.paper_agent.types import PaperTrade
from app.engines.runner_engine.crypto_learn import get_crypto_learn_config
from app.market_data.providers.bybit_derivatives import DerivativesDepth


@pytest.fixture(autouse=True)
def _reset_coeffs() -> None:
    get_crypto_learn_config().reset(persist=False)
    yield
    get_crypto_learn_config().reset(persist=False)


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


def test_v2_universe_is_sixteen() -> None:
    assert len(V2_UNIVERSE) == 16
    assert V2_UNIVERSE[-4:] == ("SUI", "ADA", "LTC", "DOT")


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


def _empty_cme(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_cme_paper_ideas",
        lambda market, min_confidence=55.0: [],
    )


def test_agent_one_symbol_skips_other_source_same_tick(monkeypatch) -> None:
    """Same-symbol: prefer L2 fade over v2 momentum, then skip the rest."""
    _empty_cme(monkeypatch)
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

    class _Crypto:
        def scan_feed(self, **_kwargs):
            return [
                SimpleNamespace(
                    symbol="BTC",
                    setup_type="funding_extreme",
                    direction_bias="short",
                    confidence=68.0,
                    factors=["Funding +9 bps"],
                ),
                SimpleNamespace(
                    symbol="ETH",
                    setup_type="funding_extreme",
                    direction_bias="long",
                    confidence=70.0,
                    factors=["Funding extreme"],
                ),
            ]

    agent = PaperAgent(
        market_data=_Market(5.0),  # type: ignore[arg-type]
        crypto_scanner=_Crypto(),  # type: ignore[arg-type]
        equity_scanner=_EmptyFeed(),  # type: ignore[arg-type]
        store=PaperTradeStore(),
        pipeline=None,
        size_usd=2500.0,
    )
    notes = agent.tick()
    assert any(n.startswith("open:BTC:funding_extreme") for n in notes)
    assert "skip:symbol_open:BTC" in notes
    assert not any(n.startswith("open:BTC:perp_momentum") for n in notes)
    assert any(n.startswith("open:ETH:funding_extreme") for n in notes)
    trades = agent.store.list_all()
    btc = [t for t in trades if t.symbol == "BTC"]
    eth = [t for t in trades if t.symbol == "ETH"]
    assert len(btc) == 1
    assert btc[0].source == "crypto_setup"
    assert btc[0].direction == "short"
    assert btc[0].policy.get("policy_id")
    assert btc[0].policy["knobs"]["max_new_opens_per_day"] == 5
    assert "policy_id=" in btc[0].notes
    assert len(eth) == 1
    assert eth[0].source == "crypto_setup"


def test_agent_skips_second_long_on_open_symbol(monkeypatch) -> None:
    """Double-long across sources is blocked the same way as fade-vs-momentum."""
    _empty_cme(monkeypatch)
    store = PaperTradeStore()
    now = datetime.now(UTC)
    store.upsert(
        PaperTrade(
            id="t-btc-v2",
            symbol="BTC",
            source="crypto_perp_v2",
            setup_type=SETUP_TYPE,
            direction="long",
            fingerprint=_fingerprint("crypto_perp_v2", "BTC", SETUP_TYPE, "long"),
            signal_at=now,
            confidence=72.0,
            opportunity_score=72.0,
            size_usd=2500.0,
            status="pending_honest",
            optimistic_entry=100.0,
            optimistic_entry_at=now,
        )
    )
    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_crypto_perp_v2",
        lambda market, min_confidence=55.0: [],
    )

    class _Crypto:
        def scan_feed(self, **_kwargs):
            return [
                SimpleNamespace(
                    symbol="BTC",
                    setup_type="funding_extreme",
                    direction_bias="long",
                    confidence=80.0,
                    factors=["Funding extreme"],
                )
            ]

    notes = PaperAgent(
        market_data=_Market(5.0),  # type: ignore[arg-type]
        crypto_scanner=_Crypto(),  # type: ignore[arg-type]
        equity_scanner=_EmptyFeed(),  # type: ignore[arg-type]
        store=store,
        pipeline=None,
        size_usd=2500.0,
    ).tick()
    assert "skip:symbol_open:BTC" in notes
    assert not any(n.startswith("open:BTC:") for n in notes)
    assert len(store.list_all()) == 1
    assert store.list_all()[0].source == "crypto_perp_v2"


def test_fingerprint_still_blocks_same_source_direction(monkeypatch) -> None:
    """Same source + setup + direction still never becomes a second candidate."""
    _empty_cme(monkeypatch)
    store = PaperTradeStore()
    now = datetime.now(UTC)
    store.upsert(
        PaperTrade(
            id="t-btc-setup",
            symbol="BTC",
            source="crypto_setup",
            setup_type="funding_extreme",
            direction="short",
            fingerprint=_fingerprint("crypto_setup", "BTC", "funding_extreme", "short"),
            signal_at=now,
            confidence=68.0,
            opportunity_score=68.0,
            size_usd=2500.0,
            status="open",
            optimistic_entry=100.0,
            optimistic_entry_at=now,
        )
    )
    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_crypto_perp_v2",
        lambda market, min_confidence=55.0: [],
    )

    class _Crypto:
        def scan_feed(self, **_kwargs):
            return [
                SimpleNamespace(
                    symbol="BTC",
                    setup_type="funding_extreme",
                    direction_bias="short",
                    confidence=90.0,
                    factors=["Funding +9 bps"],
                )
            ]

    notes = PaperAgent(
        market_data=_Market(5.0),  # type: ignore[arg-type]
        crypto_scanner=_Crypto(),  # type: ignore[arg-type]
        equity_scanner=_EmptyFeed(),  # type: ignore[arg-type]
        store=store,
        pipeline=None,
        size_usd=2500.0,
    ).tick()
    assert not any(n.startswith("open:BTC:") for n in notes)
    # Fingerprint drops the duplicate before the open loop, so symbol_open is silent.
    assert "skip:symbol_open:BTC" not in notes
    assert len(store.list_all()) == 1
    assert store.list_all()[0].fingerprint == _fingerprint(
        "crypto_setup", "BTC", "funding_extreme", "short"
    )


def test_score_symbol_skips_long_momentum_into_crowded_funding(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.crypto_perp_v2.fetch_derivatives_depth",
        lambda symbol, timeout=2.0: _depth(funding=0.0010),  # +10 bps
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
    assert score_symbol(_Market(4.0), "BTC") is None  # type: ignore[arg-type]


def test_agent_prefers_l2_over_higher_v2_score(monkeypatch) -> None:
    _empty_cme(monkeypatch)
    monkeypatch.setattr("app.engines.paper_agent.agent.MAX_NEW_OPENS_PER_DAY", 1)
    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_crypto_perp_v2",
        lambda market, min_confidence=55.0: [
            SimpleNamespace(
                symbol="SOL",
                direction="long",
                setup_type=SETUP_TYPE,
                confidence=90.0,
                factors=["12h momentum +8.0%"],
                extras={"funding_bps": 1.0},
            )
        ],
    )

    class _Crypto:
        def scan_feed(self, **_kwargs):
            return [
                SimpleNamespace(
                    symbol="ETH",
                    setup_type="funding_extreme",
                    direction_bias="short",
                    confidence=58.0,
                    factors=["Funding +8 bps"],
                )
            ]

    notes = PaperAgent(
        market_data=_Market(5.0),  # type: ignore[arg-type]
        crypto_scanner=_Crypto(),  # type: ignore[arg-type]
        equity_scanner=_EmptyFeed(),  # type: ignore[arg-type]
        store=PaperTradeStore(),
        pipeline=None,
        size_usd=2500.0,
    ).tick()
    assert any(n.startswith("open:ETH:funding_extreme") for n in notes)
    assert not any(n.startswith("open:SOL:") for n in notes)


def test_agent_skips_v2_when_funding_fights_momentum(monkeypatch) -> None:
    _empty_cme(monkeypatch)
    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_crypto_perp_v2",
        lambda market, min_confidence=55.0: [
            SimpleNamespace(
                symbol="BTC",
                direction="long",
                setup_type=SETUP_TYPE,
                confidence=80.0,
                factors=["12h momentum +5.0%"],
                extras={"funding_bps": 12.0},
            )
        ],
    )
    notes = _agent().tick()
    assert "skip:crowded_funding:BTC" in notes
    assert not any(n.startswith("open:BTC:") for n in notes)
