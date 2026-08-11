"""Unit tests for Layer 3 equity-options surface (HOOD-style)."""

from datetime import UTC, date, datetime

import pandas as pd
import pytest
from httpx import AsyncClient

from app.engines.opportunity_engine.equity_options.momentum import compute_momentum
from app.engines.opportunity_engine.equity_options.option_chain import RawOptionRow
from app.engines.opportunity_engine.equity_options.option_selector import score_option_candidates
from app.engines.opportunity_engine.equity_options.plan_builder import build_execution_plan
from app.engines.opportunity_engine.equity_options.scanner import (
    EquityOptionsScanner,
    build_idea_from_momentum,
)
from app.market_data.providers.mock import MockMarketDataProvider
from app.market_data.service import MarketDataService


def _as_of() -> datetime:
    return datetime(2026, 8, 9, 16, 0, tzinfo=UTC)


def _hood_ohlcv(bars: int = 80, last_price: float = 93.65) -> pd.DataFrame:
    """Synthetic daily bars: grind up into low-$90s with volume expansion."""
    rows = []
    price = 70.0
    base = datetime(2026, 5, 1, tzinfo=UTC)
    for i in range(bars):
        # Gentle uptrend into last_price
        t = i / max(bars - 1, 1)
        price = 70.0 + (last_price - 70.0) * t
        noise = 0.4 if i % 7 else -0.3
        open_p = price - 0.2
        high = price + 1.1 + noise
        low = price - 1.0
        close = price + noise * 0.2
        vol = 8_000_000 + (4_000_000 if i >= bars - 5 else 0)
        rows.append(
            {
                "timestamp": base + pd.Timedelta(days=i),
                "open": open_p,
                "high": high,
                "low": low,
                "close": close,
                "volume": float(vol),
            }
        )
    # Ensure final close near HOOD screenshot price
    rows[-1]["close"] = last_price
    rows[-1]["high"] = max(rows[-1]["high"], last_price + 0.5)
    rows[-1]["volume"] = 14_000_000
    return pd.DataFrame(rows)


def _hood_option_rows() -> list[RawOptionRow]:
    """Aug 28 / Sep chain around HOOD ~93.65 — includes lottery $119."""
    return [
        RawOptionRow(
            expiry="2026-08-28",
            strike=105.0,
            right="call",
            bid=1.80,
            ask=1.95,
            volume=1200,
            open_interest=8000,
            iv=0.62,
        ),
        RawOptionRow(
            expiry="2026-08-28",
            strike=110.0,
            right="call",
            bid=1.05,
            ask=1.20,
            volume=900,
            open_interest=6000,
            iv=0.65,
        ),
        RawOptionRow(
            expiry="2026-08-28",
            strike=115.0,
            right="call",
            bid=0.70,
            ask=0.85,
            volume=700,
            open_interest=4500,
            iv=0.68,
        ),
        RawOptionRow(
            expiry="2026-08-28",
            strike=119.0,
            right="call",
            bid=0.48,
            ask=0.55,
            volume=400,
            open_interest=2200,
            iv=0.72,
        ),
        RawOptionRow(
            expiry="2026-09-18",
            strike=115.0,
            right="call",
            bid=1.40,
            ask=1.55,
            volume=1100,
            open_interest=7000,
            iv=0.60,
        ),
        RawOptionRow(
            expiry="2026-08-28",
            strike=85.0,
            right="put",
            bid=1.10,
            ask=1.25,
            volume=500,
            open_interest=3000,
            iv=0.58,
        ),
    ]


def test_compute_momentum_hood_uptrend() -> None:
    snap = compute_momentum(_hood_ohlcv())
    assert snap is not None
    assert snap.price == pytest.approx(93.65, abs=0.01)
    assert snap.momentum_score >= 55
    assert snap.breakout_level is not None
    assert snap.support_level is not None


def test_option_selector_prefers_risk_adjusted_over_lottery() -> None:
    candidates = score_option_candidates(
        "HOOD",
        spot=93.65,
        direction="long",
        rows=_hood_option_rows(),
        as_of=date(2026, 8, 9),
    )
    assert len(candidates) >= 3
    best = candidates[0]
    lottery = next(c for c in candidates if c.strike == 119.0)
    # Sexiest payoff should not automatically win overall
    assert best.strike != 119.0
    assert lottery.otm_pct > best.otm_pct
    assert best.overall_score >= lottery.overall_score


def test_build_idea_and_plan_hood() -> None:
    snap = compute_momentum(_hood_ohlcv())
    assert snap is not None
    idea = build_idea_from_momentum(
        "HOOD",
        snap,
        _hood_option_rows(),
        as_of=_as_of(),
        max_risk_usd=1000.0,
    )
    assert idea is not None
    assert idea.symbol == "HOOD"
    assert idea.direction_bias == "long"
    assert idea.setup_type in {"momentum_continuation", "breakout_convexity"}
    assert idea.trade_state_hint in {"IGNORE", "WATCH"}
    assert idea.trade_state_hint != "EXECUTE"
    assert idea.selected_option is not None
    assert idea.execution_plan is not None
    assert len(idea.execution_plan.entries) == 3
    assert sum(e.size_pct for e in idea.execution_plan.entries) == pytest.approx(100.0)
    assert idea.execution_plan.max_risk_usd == 1000.0
    assert idea.execution_plan.runner_pct in {20.0, 30.0, 35.0}
    assert idea.execution_plan.runner_rule
    assert any(inv.startswith("HARD:") for inv in idea.execution_plan.invalidation)
    assert any(inv.startswith("SOFT:") for inv in idea.execution_plan.invalidation)
    assert any(
        "support" in inv.lower() or "dma" in inv.lower()
        for inv in idea.execution_plan.invalidation
    )
    assert idea.opportunity_score > 0


def test_plan_builder_standalone() -> None:
    snap = compute_momentum(_hood_ohlcv())
    assert snap is not None
    plan = build_execution_plan(
        "HOOD",
        "long",
        snap,
        None,
        setup_type="momentum_continuation",
        max_risk_usd=990.0,
    )
    assert plan.setup_name.startswith("Bullish")
    assert len(plan.profit_zones) == 3
    assert plan.max_risk_usd == 990.0
    assert plan.runner_rule
    assert any(z.label for z in plan.profit_zones)


def test_plan_builder_short_dte_harvests_earlier() -> None:
    from app.engines.opportunity_engine.equity_options.types import OptionCandidate

    snap = compute_momentum(_hood_ohlcv())
    assert snap is not None
    short = OptionCandidate(
        underlying="HOOD",
        expiry="2026-08-21",
        strike=100.0,
        right="call",
        mid=1.5,
        dte=10,
        overall_score=70.0,
    )
    plan = build_execution_plan(
        "HOOD",
        "long",
        snap,
        short,
        setup_type="breakout_convexity",
        max_risk_usd=1000.0,
    )
    assert plan.setup_name == "Bullish breakout convexity"
    assert plan.runner_pct == 20.0
    assert plan.profit_zones[0].option_gain_pct == 40.0
    assert "short DTE" in plan.notes or "Short DTE" in plan.notes


def test_scanner_crypto_empty() -> None:
    scanner = EquityOptionsScanner(
        MarketDataService(provider=MockMarketDataProvider()),
        option_fetcher=lambda _s: [],
    )
    assert scanner.scan("BTC") == []


def test_scanner_equity_with_mocks(monkeypatch) -> None:
    from app.utils.ttl_cache import TTLCache

    monkeypatch.setattr(
        "app.engines.opportunity_engine.equity_options.scanner._SCAN_CACHE",
        TTLCache(ttl_seconds=1.0),
    )

    ohlcv = _hood_ohlcv()

    class _Prov(MockMarketDataProvider):
        def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 200):
            return ohlcv.tail(limit).copy()

    scanner = EquityOptionsScanner(
        MarketDataService(provider=_Prov()),
        option_fetcher=lambda _s: _hood_option_rows(),
    )
    ideas = scanner.scan("HOOD")
    assert len(ideas) == 1
    assert ideas[0].selected_option is not None


@pytest.mark.asyncio
async def test_equity_setups_feed_endpoint(client: AsyncClient, monkeypatch) -> None:
    from app.core.service_dependencies import get_equity_options_scanner
    from app.engines.opportunity_engine.equity_options.types import (
        EquityOptionsIdea,
        ExecutionPlan,
        OptionCandidate,
        StagedEntry,
    )
    from app.main import app

    as_of = _as_of()
    idea = EquityOptionsIdea(
        id="hood-test",
        symbol="HOOD",
        setup_type="breakout_convexity",
        direction_bias="long",
        confidence=72.0,
        opportunity_score=78.0,
        factors=["5D momentum +4.2%"],
        conflicts=[],
        trade_state_hint="WATCH",
        momentum_score=74.0,
        selected_option=OptionCandidate(
            underlying="HOOD",
            expiry="2026-09-18",
            strike=115.0,
            right="call",
            mid=1.48,
            overall_score=86.0,
            rationale="12% OTM",
        ),
        execution_plan=ExecutionPlan(
            setup_name="Bullish momentum continuation",
            direction="long",
            max_risk_usd=1000.0,
            entries=[
                StagedEntry(1, "Probe", 25.0, "hold", 98.0),
                StagedEntry(2, "Confirm", 35.0, "breakout", 102.0),
                StagedEntry(3, "Expand", 40.0, "volume", 108.0),
            ],
        ),
        as_of=as_of,
        data_quality="good",
    )

    class _Stub:
        def scan_feed(self, symbols=None, *, watch_only=False, min_confidence=0.0):
            return [idea]

    app.dependency_overrides[get_equity_options_scanner] = lambda: _Stub()
    try:
        response = await client.get("/api/v1/equity-setups?watch_only=true&min_confidence=55")
    finally:
        app.dependency_overrides.pop(get_equity_options_scanner, None)

    assert response.status_code == 200
    data = response.json()
    assert data["watch_only"] is True
    assert len(data["setups"]) == 1
    assert data["setups"][0]["symbol"] == "HOOD"
    assert data["setups"][0]["selected_option"]["strike"] == 115.0
    assert data["setups"][0]["execution_plan"]["entries"][0]["size_pct"] == 25.0
    assert data["setups"][0]["trade_state_hint"] == "WATCH"


@pytest.mark.asyncio
async def test_asset_equity_setups_endpoint(client: AsyncClient, monkeypatch) -> None:
    from app.core.service_dependencies import get_equity_options_scanner
    from app.main import app

    class _Stub:
        def scan(self, symbol: str):
            return []

    app.dependency_overrides[get_equity_options_scanner] = lambda: _Stub()
    try:
        response = await client.get("/api/v1/assets/HOOD/equity-setups")
    finally:
        app.dependency_overrides.pop(get_equity_options_scanner, None)

    assert response.status_code == 200
    assert response.json()["symbol"] == "HOOD"
    assert response.json()["setups"] == []


@pytest.mark.asyncio
async def test_asset_equity_setups_unknown(client: AsyncClient) -> None:
    response = await client.get("/api/v1/assets/ZZZ/equity-setups")
    assert response.status_code == 404
