"""Runtime-active scoring weight configuration."""

from threading import Lock

from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory, validate_weights


class WeightConfig:
    """Thread-safe store for active scoring weights.

    When a non-default preset (or custom map) is applied, ``regime_auto`` is
    disabled so fixed weights win over regime profile swaps. Reset / apply
    ``default`` re-enables auto-regime.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._weights: dict[ScoringCategory, float] = dict(DEFAULT_WEIGHTS)
        self._active_preset: str = "default"
        self._regime_auto: bool = True

    def get_weights(self) -> dict[ScoringCategory, float]:
        """Return a copy of the active weights."""
        with self._lock:
            return dict(self._weights)

    def get_preset_name(self) -> str:
        """Return the name of the active preset."""
        with self._lock:
            return self._active_preset

    def is_regime_auto(self) -> bool:
        """Whether regime profile swaps are active for scoring."""
        with self._lock:
            return self._regime_auto

    def apply(self, weights: dict[ScoringCategory, float], preset_name: str = "custom") -> None:
        """Set active weights after validation.

        Non-default presets disable auto-regime; ``default`` re-enables it.
        """
        validate_weights(weights)
        with self._lock:
            self._weights = dict(weights)
            self._active_preset = preset_name
            self._regime_auto = preset_name == "default"

    def reset(self) -> None:
        """Restore default weights and re-enable auto-regime."""
        with self._lock:
            self._weights = dict(DEFAULT_WEIGHTS)
            self._active_preset = "default"
            self._regime_auto = True


_weight_config = WeightConfig()


def get_weight_config() -> WeightConfig:
    """Return the global weight configuration singleton."""
    return _weight_config
