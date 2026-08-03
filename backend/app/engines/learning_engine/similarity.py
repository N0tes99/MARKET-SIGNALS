"""Evidence vector utilities for similarity search."""

import math

from app.engines.evidence_engine.types import EvidenceBundle, EvidenceItem
from app.scoring.weights import ScoringCategory

_CATEGORY_ORDER = [c.value for c in ScoringCategory]


def evidence_to_vector(items: list[EvidenceItem]) -> list[float]:
    """Convert evidence items to a fixed-order score vector (0-100 per category)."""
    by_category = {item.category: item.score for item in items}
    return [by_category.get(category, 50.0) for category in _CATEGORY_ORDER]


def vector_from_categories(scores: dict[str, float]) -> list[float]:
    """Build a vector from a category score mapping."""
    return [scores.get(category, 50.0) for category in _CATEGORY_ORDER]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def similarity_from_evidence(current: EvidenceBundle, past_scores: dict[str, float]) -> float:
    """Similarity between current evidence and a stored category score map."""
    current_vec = evidence_to_vector(current.items)
    past_vec = vector_from_categories(past_scores)
    return cosine_similarity(current_vec, past_vec)
