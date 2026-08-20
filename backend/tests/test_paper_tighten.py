"""Tests for paper bot tightening — expansion vs momentum deferral."""

from __future__ import annotations

from datetime import UTC, datetime

from app.cortex.types import SymbolContext, WorkingMemory
from app.engines.expansion_engine.types import ExpansionState
from app.engines.paper_agent.agent import PaperAgent
from app.engines.paper_agent.crypto_perp_v2 import CryptoPerpV2Idea
from app.engines.paper_agent.squeeze_expansion import active_expansion_alert
from app.services.expansion_alert_service import ExpansionAlertService
from tests.test_squeeze_expansion import _Cortex, _EmptyFeed, _Market, _candidate


def test_active_expansion_alert_reads_cortex() -> None:
    mem = WorkingMemory(
        tick_id="t1",
        as_of=datetime.now(UTC),
        universe=("SOL",),
        symbols={
            "SOL": SymbolContext(
                symbol="SOL",
                expansion=_candidate(symbol="SOL", state=ExpansionState.PRIMED, net=82.0),
                alert_level="primed",
            )
        },
    )
    assert active_expansion_alert(_Cortex(mem), "SOL") == "primed"
    assert active_expansion_alert(_Cortex(mem), "BTC") is None


def test_expansion_alert_escalation_only() -> None:
    class _Alerts:
        sent: list[str] = []

        def send_embed(self, symbol, embed, **kwargs):
            _Alerts.sent.append(symbol)
            return True

    mem = WorkingMemory(
        tick_id="t2",
        as_of=datetime.now(UTC),
        universe=("BTC",),
        symbols={
            "BTC": SymbolContext(
                symbol="BTC",
                expansion=_candidate(symbol="BTC", state=ExpansionState.PRIMED, net=82.0),
                alert_level="primed",
            )
        },
    )
    svc = ExpansionAlertService()
    notes = svc.notify_memory(mem, _Alerts())
    assert notes == ["alert:BTC:primed"]
    assert _Alerts.sent == ["BTC"]
    # Same level again — no duplicate
    assert svc.notify_memory(mem, _Alerts()) == []


def test_agent_defers_perp_v2_when_expansion_primed(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_cme_paper_ideas", lambda *a, **k: []
    )

    def _v2_idea(*_a, **_k):
        return [
            CryptoPerpV2Idea(
                symbol="SOL",
                direction="long",
                setup_type="perp_momentum",
                confidence=88.0,
                factors=["mom"],
                extras={"funding_bps": 1.0},
            )
        ]

    monkeypatch.setattr("app.engines.paper_agent.agent.scan_crypto_perp_v2", _v2_idea)
    mem = WorkingMemory(
        tick_id="t3",
        as_of=datetime.now(UTC),
        universe=("SOL",),
        symbols={
            "SOL": SymbolContext(
                symbol="SOL",
                expansion=_candidate(symbol="SOL", state=ExpansionState.PRIMED, net=82.0),
                alert_level="primed",
            )
        },
    )
    agent = PaperAgent(
        market_data=_Market(),  # type: ignore[arg-type]
        crypto_scanner=_EmptyFeed(),  # type: ignore[arg-type]
        equity_scanner=_EmptyFeed(),  # type: ignore[arg-type]
        store=__import__(
            "app.engines.paper_agent.store", fromlist=["PaperTradeStore"]
        ).PaperTradeStore(),
        pipeline=None,
        size_usd=2500.0,
        cortex=_Cortex(mem),
    )
    notes = agent.tick()
    assert any(n.startswith("skip:expansion_active:SOL") for n in notes)
    assert not any(n.startswith("open:SOL:") for n in notes)
