"""Named weight presets for optimization experiments."""

from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory


def _normalize(raw: dict[ScoringCategory, float]) -> dict[ScoringCategory, float]:
    """Scale weights to sum to exactly 100, filling missing categories from defaults."""
    merged = {cat: raw.get(cat, DEFAULT_WEIGHTS[cat]) for cat in ScoringCategory}
    total = sum(merged.values())
    scaled = {cat: (value / total) * 100.0 for cat, value in merged.items()}
    rounded = {cat: round(value, 2) for cat, value in scaled.items()}
    drift = 100.0 - sum(rounded.values())
    if rounded:
        first = next(iter(rounded))
        rounded[first] = round(rounded[first] + drift, 2)
    return rounded


WEIGHT_PRESETS: dict[str, dict[ScoringCategory, float]] = {
    "default": dict(DEFAULT_WEIGHTS),
    "trend_focused": _normalize(
        {
            ScoringCategory.TREND: 28,
            ScoringCategory.STRUCTURE: 27,
            ScoringCategory.MOMENTUM: 10,
            ScoringCategory.VOLUME: 5,
            ScoringCategory.RISK: 12,
            ScoringCategory.MACRO: 8,
            ScoringCategory.DERIVATIVES: 10,
        }
    ),
    "momentum_focused": _normalize(
        {
            ScoringCategory.TREND: 12,
            ScoringCategory.STRUCTURE: 13,
            ScoringCategory.MOMENTUM: 28,
            ScoringCategory.VOLUME: 17,
            ScoringCategory.RISK: 12,
            ScoringCategory.MACRO: 8,
            ScoringCategory.DERIVATIVES: 10,
        }
    ),
    "risk_adjusted": _normalize(
        {
            ScoringCategory.TREND: 16,
            ScoringCategory.STRUCTURE: 16,
            ScoringCategory.MOMENTUM: 12,
            ScoringCategory.VOLUME: 8,
            ScoringCategory.RISK: 28,
            ScoringCategory.MACRO: 10,
            ScoringCategory.DERIVATIVES: 10,
        }
    ),
    "macro_aware": _normalize(
        {
            ScoringCategory.TREND: 16,
            ScoringCategory.STRUCTURE: 16,
            ScoringCategory.MOMENTUM: 12,
            ScoringCategory.VOLUME: 8,
            ScoringCategory.RISK: 12,
            ScoringCategory.MACRO: 22,
            ScoringCategory.DERIVATIVES: 14,
        }
    ),
    "structure_breakout": _normalize(
        {
            ScoringCategory.TREND: 14,
            ScoringCategory.STRUCTURE: 32,
            ScoringCategory.MOMENTUM: 18,
            ScoringCategory.VOLUME: 12,
            ScoringCategory.RISK: 10,
            ScoringCategory.MACRO: 7,
            ScoringCategory.DERIVATIVES: 7,
        }
    ),
    "volume_confirmed": _normalize(
        {
            ScoringCategory.TREND: 16,
            ScoringCategory.STRUCTURE: 14,
            ScoringCategory.MOMENTUM: 14,
            ScoringCategory.VOLUME: 26,
            ScoringCategory.RISK: 12,
            ScoringCategory.MACRO: 8,
            ScoringCategory.DERIVATIVES: 10,
        }
    ),
    "derivatives_heavy": _normalize(
        {
            ScoringCategory.TREND: 14,
            ScoringCategory.STRUCTURE: 14,
            ScoringCategory.MOMENTUM: 12,
            ScoringCategory.VOLUME: 8,
            ScoringCategory.RISK: 12,
            ScoringCategory.MACRO: 10,
            ScoringCategory.DERIVATIVES: 30,
        }
    ),
}
