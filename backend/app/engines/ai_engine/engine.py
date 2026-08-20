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

_GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"
_GEMINI_MODEL = "gemini-2.0-flash"


@dataclass
class AIExplanation:
    """Human-readable analysis generated from numerical evidence."""

    symbol: str
    summary: str
    confidence: float
    factors: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    source: str = "local"  # local | openai | gemini
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class AIAnalyst:
    """Generates explainable, human-readable analysis from evidence and decisions.

    Uses OpenAI when ``OPENAI_API_KEY`` is set, else Gemini when
    ``GEMINI_API_KEY`` is set (free AI Studio quota). Otherwise a local
    synthesizer over the same evidence (Fear & Greed, Reddit, tape).
    """

    def explain_decision(self, decision: DecisionResult) -> AIExplanation:
        """Generate an explanation from a full pipeline decision."""
        backend = _llm_backend()
        if backend is not None:
            client, model, source = backend
            try:
                return self._explain_with_llm(decision, client, model, source)
            except Exception:
                logger.exception(
                    "%s explanation failed for %s, using local",
                    source,
                    decision.symbol,
                )

        return self._explain_locally(decision)

    def explain_evidence(
        self,
        symbol: str,
        evidence: EvidenceBundle,
        confidence: float | None = None,
    ) -> AIExplanation:
        """Generate an explanation from an evidence bundle alone."""
        conf = confidence if confidence is not None else evidence.total_confidence
        factors = self._ordered_factors(evidence.items)
        conflicts = self._detect_conflicts(evidence.items)
        return AIExplanation(
            symbol=symbol.upper(),
            summary=self._synthesize_summary(
                symbol=symbol.upper(),
                confidence=conf,
                grade=None,
                trade_state=None,
                execution=None,
                items=evidence.items,
                conflicts=conflicts,
            ),
            confidence=conf,
            factors=factors,
            conflicts=conflicts,
            source="local",
        )

    def _explain_locally(self, decision: DecisionResult) -> AIExplanation:
        """Build a rule-based explanation without external API calls."""
        evidence = decision.evidence
        conflicts = self._detect_conflicts(evidence.items)
        summary = self._synthesize_summary(
            symbol=decision.symbol,
            confidence=evidence.total_confidence,
            grade=decision.opportunity.trade_grade,
            trade_state=decision.trade_state.value,
            execution=decision.execution.signal.value,
            items=evidence.items,
            conflicts=conflicts,
        )
        return AIExplanation(
            symbol=decision.symbol,
            summary=summary,
            confidence=evidence.total_confidence,
            factors=self._ordered_factors(evidence.items),
            conflicts=conflicts,
            source="local",
        )

    def _explain_with_llm(
        self,
        decision: DecisionResult,
        client: OpenAI,
        model: str,
        source: str,
    ) -> AIExplanation:
        """Generate explanation via OpenAI-compatible chat from evidence JSON."""
        payload = _decision_payload(decision)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Signal Engine's AI Analyst. You explain market evidence "
                        "to traders. You NEVER give buy/sell commands. Lead with how "
                        "crowd sentiment (Fear & Greed, Reddit) lines up or fights the "
                        "tape (trend, momentum, events). Summarize evidence, highlight "
                        "supporting factors, and flag conflicts. Respond in JSON with "
                        "keys: summary (2-3 sentences), factors (array of bullet strings), "
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
            max_tokens=600,
        )

        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        conflicts = parsed.get("conflicts") or self._detect_conflicts(decision.evidence.items)
        factors = parsed.get("factors") or self._ordered_factors(decision.evidence.items)

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
            factors=list(factors)[:8],
            conflicts=list(conflicts)[:6],
            source=source,
        )

    def _ordered_factors(self, items: list[EvidenceItem]) -> list[str]:
        """Prefer crowd + tape evidence over a raw score dump."""
        preferred = (
            "Sentiment",
            "Trend",
            "Momentum",
            "Events",
            "Volatility",
            "Risk",
            "Derivatives",
        )
        by_cat: dict[str, list[EvidenceItem]] = {}
        for item in items:
            by_cat.setdefault(item.category, []).append(item)

        picked: list[str] = []
        seen: set[str] = set()
        for cat in preferred:
            for item in by_cat.get(cat, []):
                if item.score <= 0 and not item.description:
                    continue
                line = self._format_factor(item)
                if line not in seen:
                    picked.append(line)
                    seen.add(line)
        for item in items:
            line = self._format_factor(item)
            if line not in seen and item.description:
                picked.append(line)
                seen.add(line)
        return picked[:8]

    def _synthesize_summary(
        self,
        *,
        symbol: str,
        confidence: float,
        grade: str | None,
        trade_state: str | None,
        execution: str | None,
        items: list[EvidenceItem],
        conflicts: list[str],
    ) -> str:
        """Two-to-three sentence local write-up from F&G, Reddit, and tape."""
        crowd = _crowd_line(items)
        tape = _tape_line(items)
        headline_bits = [f"{symbol} scored {confidence:.0f}%"]
        if grade:
            headline_bits.append(f"grade {grade}")
        if trade_state:
            headline_bits.append(f"state {trade_state}")
        headline = ", ".join(headline_bits) + "."
        if execution:
            headline += f" Execution hint: {execution}."

        parts = [headline]
        if crowd:
            parts.append(crowd)
        if tape:
            parts.append(tape)
        if conflicts:
            parts.append(f"Watch: {conflicts[0]}.")
        elif not crowd and not tape:
            parts.append(self._local_summary(symbol, confidence, []))
        return " ".join(parts)

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
        """Flag opposing signals across categories and crowd vs tape."""
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
        if volatility <= 40 and sentiment <= 40:
            conflicts.append("Elevated VIX alongside extreme greed (Fear & Greed)")
        if volatility >= 56 and sentiment >= 60:
            conflicts.append("Calm VIX alongside extreme fear (Fear & Greed divergence)")

        fng = _item_by_source(items, "sentiment_engine")
        reddit = _item_by_source(items, "reddit_social")
        fng_text = (fng.description if fng else "").lower()
        reddit_text = (reddit.description if reddit else "").lower()

        if "extreme greed" in fng_text and trend >= 60:
            conflicts.append("Tape is bid while Fear & Greed is extreme greed — crowded long risk")
        if "crowded" in reddit_text and trend >= 60:
            conflicts.append("Bullish tape into crowded Reddit chatter — chase risk")
        if "fearful" in reddit_text and trend <= 40:
            conflicts.append("Bearish tape plus fearful Reddit — crowd already leaning short")
        if fng is not None and reddit is not None and reddit.score > 0:
            if fng.score <= 40 and reddit.score >= 56:
                conflicts.append("Fear & Greed is greedy while Reddit is fearful — crowd split")
            if fng.score >= 60 and reddit.score <= 42:
                conflicts.append(
                    "Fear & Greed is fearful while Reddit is crowded-bullish — crowd split"
                )

        return conflicts


def _item_by_source(items: list[EvidenceItem], source: str) -> EvidenceItem | None:
    for item in items:
        if item.source == source:
            return item
    return None


def _crowd_line(items: list[EvidenceItem]) -> str:
    fng = _item_by_source(items, "sentiment_engine")
    reddit = _item_by_source(items, "reddit_social")
    bits: list[str] = []
    if fng and fng.description:
        bits.append(fng.description.rstrip("."))
    if reddit and reddit.description and "unavailable" not in reddit.description.lower():
        bits.append(reddit.description.rstrip("."))
    if not bits:
        return ""
    return "Crowd: " + "; ".join(bits) + "."


def _tape_line(items: list[EvidenceItem]) -> str:
    wanted = ("Trend", "Momentum", "Events")
    bits: list[str] = []
    for cat in wanted:
        for item in items:
            if item.category == cat and item.description:
                bits.append(f"{cat} {item.score:.0f}% ({item.description.rstrip('.')})")
                break
    if not bits:
        return ""
    return "Tape: " + "; ".join(bits) + "."


def _decision_payload(decision: DecisionResult) -> dict:
    crowd = [
        {
            "source": item.source,
            "score": item.score,
            "description": item.description,
        }
        for item in decision.evidence.items
        if item.source in {"sentiment_engine", "reddit_social"} or item.category == "Sentiment"
    ]
    return {
        "symbol": decision.symbol,
        "confidence": decision.evidence.total_confidence,
        "trade_grade": decision.opportunity.trade_grade,
        "trade_state": decision.trade_state.value,
        "execution_signal": decision.execution.signal.value,
        "expected_value": decision.opportunity.expected_value,
        "crowd_sentiment": crowd,
        "evidence": [
            {
                "category": item.category,
                "source": item.source,
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


def get_llm_backend() -> tuple[OpenAI, str, str] | None:
    """Return (client, model, source). OpenAI if paid key set, else free Gemini."""
    return _llm_backend()


def _llm_backend() -> tuple[OpenAI, str, str] | None:
    """Return (client, model, source). OpenAI if paid key set, else free Gemini."""
    openai_key = settings.openai_api_key.strip()
    if openai_key:
        return OpenAI(api_key=openai_key), "gpt-4o-mini", "openai"
    gemini_key = settings.gemini_api_key.strip()
    if gemini_key:
        return (
            OpenAI(api_key=gemini_key, base_url=_GEMINI_OPENAI_BASE),
            _GEMINI_MODEL,
            "gemini",
        )
    return None
