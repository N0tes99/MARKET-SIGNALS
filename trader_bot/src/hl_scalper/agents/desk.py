from __future__ import annotations

from typing import Any

import httpx

from hl_scalper.agents.coordinator import EnsembleCoordinator, summarize_votes
from hl_scalper.agents.protocol import DeskDecision, MarketSnapshot, Proposal
from hl_scalper.agents.specialists import (
    FundingAgent,
    ImbalanceAgent,
    LiquidityAgent,
    SpreadMicroAgent,
)
from hl_scalper.config import Settings
from hl_scalper.feed import L2Book
from hl_scalper.risk import RiskGate


class FundingCache:
    """TTL cache for HL metaAndAssetCtxs funding/premium."""

    def __init__(self, *, info_url: str, ttl_s: float = 15.0) -> None:
        self._url = info_url.rstrip("/")
        self._ttl = ttl_s
        self._ts = 0.0
        self._by_coin: dict[str, dict[str, float | None]] = {}

    def refresh(self, now: float) -> None:
        if now - self._ts < self._ttl and self._by_coin:
            return
        with httpx.Client(timeout=8.0) as client:
            response = client.post(self._url, json={"type": "metaAndAssetCtxs"})
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, list) or len(payload) < 2:
            return
        meta, ctxs = payload[0], payload[1]
        if not isinstance(meta, dict) or not isinstance(ctxs, list):
            return
        universe = meta.get("universe")
        if not isinstance(universe, list):
            return
        out: dict[str, dict[str, float | None]] = {}
        for idx, item in enumerate(universe):
            if not isinstance(item, dict) or idx >= len(ctxs):
                continue
            name = str(item.get("name") or "").upper()
            ctx = ctxs[idx] if isinstance(ctxs[idx], dict) else {}
            out[name] = {
                "funding": _f(ctx.get("funding")),
                "premium": _f(ctx.get("premium")),
                "mark_px": _f(ctx.get("markPx")),
                "open_interest": _f(ctx.get("openInterest")),
            }
        self._by_coin = out
        self._ts = now

    def for_coin(self, coin: str, now: float) -> dict[str, float | None]:
        self.refresh(now)
        return self._by_coin.get(coin.upper(), {})


def _f(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


class AgentDesk:
    """Run all specialists → coordinator → risk veto."""

    def __init__(self, settings: Settings, risk: RiskGate) -> None:
        self.settings = settings
        self.risk = risk
        self.funding = FundingCache(info_url=settings.info_url)
        self.agents = [
            ImbalanceAgent(settings),
            FundingAgent(extreme=settings.funding_extreme),
            LiquidityAgent(settings),
            SpreadMicroAgent(tight_bps=settings.spread_micro_tight_bps),
        ]
        self.coordinator = EnsembleCoordinator(min_agree=settings.ensemble_min_agree)

    def evaluate_coin(self, book: L2Book, *, now: float) -> DeskDecision:
        ctx = self.funding.for_coin(book.coin, now)
        snap = MarketSnapshot(
            book=book,
            funding=ctx.get("funding"),
            premium=ctx.get("premium"),
            mark_px=ctx.get("mark_px"),
            open_interest=ctx.get("open_interest"),
        )
        proposals: list[Proposal] = [agent.propose(snap) for agent in self.agents]
        decision = self.coordinator.decide(proposals)

        if decision.action != "enter" or decision.signal is None:
            return decision

        # Hard risk veto — never bypassed by ensemble agreement.
        gate = self.risk.check(decision.signal, book_age_s=book.age_s)
        if not gate.allowed:
            return DeskDecision(
                "sit_out",
                reason=f"risk_veto:{gate.reason}",
                proposals=decision.proposals
                + [Proposal("risk", "veto", reason=gate.reason)],
                agreeing_agents=decision.agreeing_agents,
            )
        return decision

    def journal_payload(self, decision: DeskDecision) -> dict[str, Any]:
        return {
            "action": decision.action,
            "side": decision.side,
            "reason": decision.reason,
            "agreeing": decision.agreeing_agents,
            "votes": summarize_votes(decision.proposals),
            "proposals": [
                {
                    "agent": p.agent,
                    "kind": p.kind,
                    "side": p.side,
                    "confidence": p.confidence,
                    "reason": p.reason,
                }
                for p in decision.proposals
            ],
        }
