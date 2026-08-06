"""AI Analyst — converts numerical evidence into human-readable reasoning."""

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from openai import OpenAI

from app.config import settings
from app.engines.evidence_engine.types import EvidenceBundle, EvidenceItem
from app.services.decision_pipeline import DecisionResult

logger = logging.getLogger(__name__)


@dataclass
class AIExplanation:
    """Human-readable analysis generated from numerical evidence."""

    symbol: str
    summary: str
    confidence: float
    factors: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    source: str = "local"  # "local" or "openai"
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class AIAnalyst:
    """Generates explainable, human-readable analysis from evidence and decisions.

    Uses OpenAI when ``OPENAI_API_KEY`` is configured; otherwise builds a
    deterministic local explanation from evidence factors.
    """

    def explain_decision(self, decision: DecisionResult) -> AIExplanation:
        """Generate an explanation from a full pipeline decision."""
        if settings.openai_api_key.strip():
            try:
                return self._explain_with_openai(decision)
            except Exception:
                logger.exception("OpenAI explanation failed for %s, using local", decision.symbol)

        return self._explain_locally(decision)

    def explain_evidence(
        self,
        symbol: str,
        evidence: EvidenceBundle,
        confidence: float | None = None,
    ) -> AIExplanation:
        """Generate an explanation from an evidence bundle alone."""
        conf = confidence if confidence is not None else evidence.total_confidence
        factors = [self._format_factor(item) for item in evidence.items if item.score > 0]
        if not factors:
            factors = [item.description for item in evidence.items[:5]]

        return AIExplanation(
            symbol=symbol.upper(),
            summary=self._local_summary(symbol, conf, factors),
            confidence=conf,
            factors=factors,
            conflicts=self._detect_conflicts(evidence.items),
            source="local",
        )

    def _explain_locally(self, decision: DecisionResult) -> AIExplanation:
        """Build a rule-based explanation without external API calls."""
        evidence = decision.evidence
        factors = [
            self._format_factor(item)
            for item in evidence.items
            if item.score >= 40
        ]
        if not factors:
            factors = [item.description for item in evidence.items if item.description]

        conflicts = self._detect_conflicts(evidence.items)
        summary = (
            f"{decision.symbol} scored {evidence.total_confidence:.0f}% "
            f"(grade {decision.opportunity.trade_grade}, state {decision.trade_state.value}). "
            f"Execution signal: {decision.execution.signal.value}. "
            f"{decision.summary.split(' — ')[0]}."
        )

        return AIExplanation(
            symbol=decision.symbol,
            summary=summary,
            confidence=evidence.total_confidence,
            factors=factors[:6],
            conflicts=conflicts,
            source="local",
        )

    def _explain_with_openai(self, decision: DecisionResult) -> AIExplanation:
        """Generate explanation via OpenAI from structured evidence JSON."""
        client = OpenAI(api_key=settings.openai_api_key)
        payload = {
            "symbol": decision.symbol,
            "confidence": decision.evidence.total_confidence,
            "trade_grade": decision.opportunity.trade_grade,
            "trade_state": decision.trade_state.value,
            "execution_signal": decision.execution.signal.value,
            "expected_value": decision.opportunity.expected_value,
            "evidence": [
                {
                    "category": item.category,
                    "score": item.score,
                    "weight": item.weight,
                    "description": item.description,
                }
                for item in decision.evidence.items
            ],
            "risk": {
                "stop_loss": decision.risk.stop_loss,
                "take_profit": decision.risk.take_profit,
                "risk_reward_ratio": decision.risk.risk_reward_ratio,
            }
            if decision.risk
            else None,
        }

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Signal Engine's AI Analyst. You explain market evidence "
                        "to traders. You NEVER give buy/sell commands. You summarize evidence, "
                        "highlight supporting factors, and flag conflicts. Respond in JSON with "
                        "keys: summary (1-2 sentences), factors (array of bullet strings), "
                        "conflicts (array of opposing signals, may be empty)."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Explain this evidence bundle:\n{json.dumps(payload, indent=2)}",
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=500,
        )

        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)

        return AIExplanation(
            symbol=decision.symbol,
            summary=parsed.get(
                "summary",
                self._local_summary(
                    decision.symbol,
                    decision.evidence.total_confidence,
                    [],
                ),
            ),
            confidence=decision.evidence.total_confidence,
            factors=parsed.get("factors", []),
            conflicts=parsed.get("conflicts", []),
            source="openai",
        )

    def _format_factor(self, item: EvidenceItem) -> str:
        """Format a single evidence item as a readable factor."""
        return f"{item.category} ({item.score:.0f}%): {item.description}"

    def _local_summary(self, symbol: str, confidence: float, factors: list[str]) -> str:
        """Build a simple local summary string."""
        if factors:
            top = factors[0].split(":")[0]
            return f"{symbol} scored {confidence:.0f}% — strongest signal in {top}."
        return f"{symbol} scored {confidence:.0f}% — insufficient evidence for strong conviction."

    def _detect_conflicts(self, items: list[EvidenceItem]) -> list[str]:
        """Flag opposing signals across categories."""
        conflicts: list[str] = []
        by_category = {item.category: item.score for item in items}

        trend = by_category.get("Trend", 50)
        momentum = by_category.get("Momentum", 50)
        macro = by_category.get("Macro", 50)
        volatility = by_category.get("Volatility", 50)
        events = by_category.get("Events", 50)
        sentiment = by_category.get("Sentiment", 50)

        if trend >= 60 and macro <= 40:
            conflicts.append("Bullish trend conflicts with weak macro backdrop")
        if trend <= 40 and momentum >= 60:
            conflicts.append("Bearish trend but strong short-term momentum")
        if trend >= 60 and momentum <= 40:
            conflicts.append("Bullish trend lacks momentum confirmation")
        if trend >= 60 and events <= 42:
            conflicts.append("Bullish trend into imminent event risk window")
        if trend >= 60 and volatility <= 40:
            conflicts.append("Bullish trend during elevated market fear (VIX)")
        # Fear & Greed vs VIX — greed into fear, or fear into calm
        if volatility <= 40 and sentiment <= 40:
            conflicts.append("Elevated VIX alongside extreme greed (Fear & Greed)")
        if volatility >= 56 and sentiment >= 60:
            conflicts.append("Calm VIX alongside extreme fear (Fear & Greed divergence)")

        return conflicts
