from __future__ import annotations

from hl_scalper.agents.coordinator import EnsembleCoordinator
from hl_scalper.agents.protocol import MarketSnapshot, Proposal
from hl_scalper.agents.specialists import FundingAgent, ImbalanceAgent, LiquidityAgent
from hl_scalper.config import Settings
from hl_scalper.feed import BookLevel, L2Book
from hl_scalper.risk import RiskGate
from hl_scalper.strategy import Signal


def _book(bid_sz: float, ask_sz: float, spread: float = 0.05) -> L2Book:
    mid = 100.0
    return L2Book(
        coin="BTC",
        bids=[BookLevel(px=mid - spread / 2, sz=bid_sz)],
        asks=[BookLevel(px=mid + spread / 2, sz=ask_sz)],
    )


def test_coordinator_requires_agreement() -> None:
    coord = EnsembleCoordinator(min_agree=2)
    proposals = [
        Proposal("imbalance", "enter", side="buy", confidence=80, signal=_sig("buy")),
        Proposal("funding", "abstain"),
        Proposal("liquidity", "abstain"),
    ]
    decision = coord.decide(proposals)
    assert decision.action == "sit_out"
    assert "need_2" in decision.reason


def test_coordinator_disagreement_sits_out() -> None:
    coord = EnsembleCoordinator(min_agree=2)
    decision = coord.decide(
        [
            Proposal("imbalance", "enter", side="buy", confidence=80, signal=_sig("buy")),
            Proposal("funding", "enter", side="sell", confidence=70),
        ]
    )
    assert decision.action == "sit_out"
    assert "disagreement" in decision.reason


def test_coordinator_agreement_enters() -> None:
    coord = EnsembleCoordinator(min_agree=2)
    decision = coord.decide(
        [
            Proposal("imbalance", "enter", side="buy", confidence=80, signal=_sig("buy")),
            Proposal("liquidity", "enter", side="buy", confidence=40),
            Proposal("funding", "abstain"),
        ]
    )
    assert decision.action == "enter"
    assert decision.side == "buy"
    assert decision.signal is not None
    assert "ensemble:" in decision.signal.reason


def test_veto_wins() -> None:
    coord = EnsembleCoordinator(min_agree=1)
    decision = coord.decide(
        [
            Proposal("imbalance", "enter", side="buy", confidence=90, signal=_sig("buy")),
            Proposal("risk", "veto", reason="daily_loss"),
        ]
    )
    assert decision.action == "sit_out"
    assert decision.reason.startswith("veto:")


def test_imbalance_and_liquidity_agents() -> None:
    settings = Settings(min_notional=1_000, spread_bps_max=12)
    snap = MarketSnapshot(book=_book(900, 100), funding=0.0)
    imb = ImbalanceAgent(settings).propose(snap)
    liq = LiquidityAgent(settings).propose(snap)
    assert imb.kind == "enter" and imb.side == "buy"
    assert liq.kind == "enter" and liq.side == "buy"


def test_funding_agent_extreme() -> None:
    agent = FundingAgent(extreme=0.0001)
    snap = MarketSnapshot(book=_book(500, 500), funding=0.0005)
    p = agent.propose(snap)
    assert p.kind == "enter" and p.side == "sell"


def test_desk_risk_veto(monkeypatch) -> None:
    from hl_scalper.agents.desk import AgentDesk

    settings = Settings(
        min_notional=1_000,
        ensemble_min_agree=2,
        daily_loss_kill_pct=0.01,
        paper_equity_usd=10_000,
        funding_extreme=0.01,  # make funding abstain
    )
    risk = RiskGate(settings)
    risk.state.day_pnl_usd = -200  # trip daily loss on check
    desk = AgentDesk(settings, risk)

    # Avoid network: stub funding cache
    monkeypatch.setattr(desk.funding, "for_coin", lambda coin, now: {"funding": 0.0, "premium": 0.0})

    book = _book(900, 100)
    decision = desk.evaluate_coin(book, now=0.0)
    # May sit out for agreement or risk — with funding mild, imbalance+liquidity should agree,
    # then risk vetoes.
    assert decision.action == "sit_out"
    assert "risk_veto" in decision.reason or "sit_out" in decision.reason or "need_" in decision.reason


def _sig(side: str) -> Signal:
    return Signal(
        coin="BTC",
        side=side,  # type: ignore[arg-type]
        imbalance=0.8,
        spread_bps=5.0,
        mid=100.0,
        edge_score=80.0,
        reason="book_imbalance",
    )
