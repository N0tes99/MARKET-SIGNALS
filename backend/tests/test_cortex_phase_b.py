"""Cortex Phase B specialists — CVD proxy, news calendar, global macro."""

from app.cortex.attention import should_run_global_macro, specialists_for_state
from app.cortex.lifecycle import assess_health
from app.cortex.specialists import (
    collect_cvd_opinion,
    collect_macro_opinion,
    collect_news_opinion,
)
from app.engines.buyer_seller_engine.engine import OrderFlowResult
from app.engines.event_engine.engine import EventSnapshot
from app.engines.expansion_engine.types import ExpansionState
from app.engines.macro_engine.engine import MacroSnapshot


class _Cvd:
    def analyze(self, symbol: str, timeframe: str = "1h") -> OrderFlowResult:
        del timeframe
        return OrderFlowResult(
            symbol=symbol,
            buyer_strength=70.0,
            seller_strength=30.0,
            absorption=80.0,
            momentum=55.0,
            volume_ratio=1.4,
            description=f"{symbol}: buyers",
        )


class _News:
    def snapshot(self, symbol: str, *, include_earnings: bool = False) -> EventSnapshot:
        del symbol, include_earnings
        return EventSnapshot(
            events=["CPI today"],
            nearest_days=0.2,
            score=35.0,
            description="Events: CPI today",
        )


class _Macro:
    def snapshot(self) -> MacroSnapshot:
        return MacroSnapshot(dxy=105.0, score=40.0, description="Macro: DXY 105")


def test_attention_includes_phase_b_specialists() -> None:
    specs = specialists_for_state(ExpansionState.DORMANT)
    assert "cvd" in specs
    assert "news" in specs
    assert "expansion" in specs
    assert should_run_global_macro() is True


def test_cvd_opinion_is_marked_proxy() -> None:
    op = collect_cvd_opinion(_Cvd(), "BTC")  # type: ignore[arg-type]
    assert op.specialist == "cvd"
    assert op.score == 70.0
    assert op.metadata["proxy"] is True
    assert op.direction == "up"


def test_news_opinion_flags_imminent_event() -> None:
    op = collect_news_opinion(_News(), "SOL")  # type: ignore[arg-type]
    assert op.specialist == "news"
    assert op.conflicts
    assert "Imminent" in op.conflicts[0]


def test_macro_opinion_is_global() -> None:
    op = collect_macro_opinion(_Macro())  # type: ignore[arg-type]
    assert op.specialist == "macro"
    assert op.direction == "down"
    assert op.metadata["dxy"] == 105.0


def test_health_reports_empty_store() -> None:
    health = assess_health(last_tick_at=None, ticks_recorded=0, backend="memory")
    assert health.healthy is False
    assert "No cortex tick yet" in health.notes
