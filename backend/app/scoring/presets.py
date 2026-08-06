"""Named weight presets for optimization experiments."""

from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory, _normalize


def _preset_normalize(raw: dict[ScoringCategory, float]) -> dict[ScoringCategory, float]:
    """Scale weights to sum to exactly 100, filling missing categories from defaults."""
    merged = {cat: raw.get(cat, DEFAULT_WEIGHTS[cat]) for cat in ScoringCategory}
    return _normalize(merged)


WEIGHT_PRESETS: dict[str, dict[ScoringCategory, float]] = {
    "default": dict(DEFAULT_WEIGHTS),
    "trend_focused": _preset_normalize(
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
    "momentum_focused": _preset_normalize(
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
    "risk_adjusted": _preset_normalize(
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
    "macro_aware": _preset_normalize(
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
    "structure_breakout": _preset_normalize(
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
    "volume_confirmed": _preset_normalize(
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
    "derivatives_heavy": _preset_normalize(
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
