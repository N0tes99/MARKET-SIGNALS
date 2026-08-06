"""Crypto fear & greed sentiment engine."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.engines.evidence_engine.types import EvidenceItem
from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory
from app.utils.scoring_helpers import clamp_score
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_FNG_URL = "https://api.alternative.me/fng/"
_FNG_CACHE: TTLCache[tuple[int, str] | None] = TTLCache(ttl_seconds=900.0)


@dataclass
class SentimentResult:
    """Fear & Greed sentiment output."""

    value: int | None
    classification: str | None
    score: float
    description: str


def score_from_fear_greed(value: int, classification: str) -> tuple[float, str]:
    """Contrarian-leaning map: extreme fear supportive, extreme greed caution."""
    if value <= 20:
        return (
            clamp_score(64.0),
            f"Fear & Greed {value} ({classification}) — extreme fear, contrarian supportive",
        )
    if value <= 40:
        return clamp_score(56.0), f"Fear & Greed {value} ({classification}) — fear zone"
    if value <= 55:
        return clamp_score(50.0), f"Fear & Greed {value} ({classification}) — neutral sentiment"
    if value <= 75:
        return clamp_score(42.0), f"Fear & Greed {value} ({classification}) — greed, crowded risk"
    return clamp_score(34.0), f"Fear & Greed {value} ({classification}) — extreme greed, caution"


def fetch_fear_greed() -> tuple[int, str] | None:
    """Fetch Crypto Fear & Greed Index (cached ~15 min)."""

    def _load() -> tuple[int, str] | None:
        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.get(_FNG_URL, params={"limit": 1})
                response.raise_for_status()
                data = response.json()["data"][0]
            return int(data["value"]), str(data["value_classification"])
        except Exception:
            logger.exception("Fear & Greed fetch failed")
            return None

    return _FNG_CACHE.get_or_set("fng", _load)


class SentimentEngine:
    """Market-wide crypto Fear & Greed as a confirmation / conflict gauge."""

    def analyze(self) -> SentimentResult:
        """Return current Fear & Greed assessment."""
        payload = fetch_fear_greed()
        if payload is None:
            return SentimentResult(
                value=None,
                classification=None,
                score=50.0,
                description="Sentiment: Fear & Greed unavailable — neutral",
            )

        value, classification = payload
        score, description = score_from_fear_greed(value, classification)
        return SentimentResult(
            value=value,
            classification=classification,
            score=score,
            description=description,
        )

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return sentiment evidence (global)."""
        del symbol, timeframe
        result = self.analyze()
        return [
            EvidenceItem(
                source="sentiment_engine",
                category=ScoringCategory.SENTIMENT.value,
                score=result.score,
                weight=DEFAULT_WEIGHTS[ScoringCategory.SENTIMENT],
                description=result.description,
            )
        ]
