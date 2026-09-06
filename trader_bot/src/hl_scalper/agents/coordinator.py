from __future__ import annotations

from collections import Counter

from hl_scalper.agents.protocol import DeskDecision, Proposal, SpecialistAgent
from hl_scalper.strategy import Side, Signal


class EnsembleCoordinator:
    """Merge specialist proposals. Disagreement or veto → sit out.

    Rules (capital-preservation first):
    1. Any veto → sit_out
    2. Any explicit sit_out → sit_out
    3. Opposing enter sides → sit_out (do not average)
    4. Need >= min_agree enter votes on the same side
    5. Prefer the Signal object from the highest-confidence enter on that side
    """

    def __init__(self, *, min_agree: int = 2) -> None:
        self.min_agree = max(1, min_agree)

    def decide(self, proposals: list[Proposal]) -> DeskDecision:
        if not proposals:
            return DeskDecision("sit_out", reason="no_proposals", proposals=[])

        for p in proposals:
            if p.kind == "veto":
                return DeskDecision(
                    "sit_out",
                    reason=f"veto:{p.agent}:{p.reason}",
                    proposals=list(proposals),
                )
            if p.kind == "sit_out":
                return DeskDecision(
                    "sit_out",
                    reason=f"sit_out:{p.agent}:{p.reason}",
                    proposals=list(proposals),
                )

        enters = [p for p in proposals if p.kind == "enter" and p.side is not None]
        if not enters:
            return DeskDecision("sit_out", reason="no_enters", proposals=list(proposals))

        sides = {p.side for p in enters}
        if len(sides) > 1:
            return DeskDecision(
                "sit_out",
                reason="disagreement:" + ",".join(sorted(f"{p.agent}:{p.side}" for p in enters)),
                proposals=list(proposals),
            )

        side: Side = next(iter(sides))  # type: ignore[assignment]
        agreeing = [p for p in enters if p.side == side]
        if len(agreeing) < self.min_agree:
            return DeskDecision(
                "sit_out",
                reason=f"need_{self.min_agree}_agree_have_{len(agreeing)}",
                proposals=list(proposals),
                agreeing_agents=[p.agent for p in agreeing],
            )

        best = max(agreeing, key=lambda p: p.confidence)
        signal = best.signal
        if signal is None:
            # Synthesize a minimal signal from the best voter for execution sizing.
            # Mid/spread come from another agent's signal if present.
            donor = next((p.signal for p in agreeing if p.signal is not None), None)
            if donor is None:
                return DeskDecision(
                    "sit_out",
                    reason="agree_but_no_signal",
                    proposals=list(proposals),
                    agreeing_agents=[p.agent for p in agreeing],
                )
            signal = Signal(
                coin=donor.coin,
                side=side,
                imbalance=donor.imbalance,
                spread_bps=donor.spread_bps,
                mid=donor.mid,
                edge_score=best.confidence,
                reason=f"ensemble:{best.agent}",
            )
        else:
            # Tag ensemble provenance without losing scores.
            signal = Signal(
                coin=signal.coin,
                side=side,
                imbalance=signal.imbalance,
                spread_bps=signal.spread_bps,
                mid=signal.mid,
                edge_score=signal.edge_score,
                reason=f"ensemble:{'+'.join(p.agent for p in agreeing)}",
            )

        return DeskDecision(
            "enter",
            side=side,
            signal=signal,
            reason=f"agree_{len(agreeing)}",
            proposals=list(proposals),
            agreeing_agents=[p.agent for p in agreeing],
        )


def summarize_votes(proposals: list[Proposal]) -> dict[str, object]:
    kinds = Counter(p.kind for p in proposals)
    sides = Counter(p.side for p in proposals if p.side)
    return {
        "kinds": dict(kinds),
        "sides": {str(k): v for k, v in sides.items()},
        "agents": [p.agent for p in proposals],
    }
