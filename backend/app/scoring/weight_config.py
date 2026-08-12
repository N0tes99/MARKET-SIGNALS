"""Runtime-active scoring weight configuration."""

from threading import Lock

from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory, validate_weights


class WeightConfig:
    """Thread-safe store for active scoring weights.

    When a non-default preset (or custom map) is applied, ``regime_auto`` is
    disabled so fixed weights win over regime profile swaps. Reset / apply
    ``default`` re-enables auto-regime. Apply/reset persist to Postgres when
    available so the desk is not process-local.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._weights: dict[ScoringCategory, float] = dict(DEFAULT_WEIGHTS)
        self._active_preset: str = "default"
        self._regime_auto: bool = True
        self._hydrated: bool = False

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

    def apply(
        self,
        weights: dict[ScoringCategory, float],
        preset_name: str = "custom",
        *,
        persist: bool = True,
    ) -> None:
        """Set active weights after validation.

        Non-default presets disable auto-regime; ``default`` re-enables it.
        """
        validate_weights(weights)
        with self._lock:
            self._weights = dict(weights)
            self._active_preset = preset_name
            self._regime_auto = preset_name == "default"
            snapshot = (self._active_preset, dict(self._weights), self._regime_auto)
        if persist:
            self._persist(*snapshot)

    def reset(self, *, persist: bool = True) -> None:
        """Restore default weights and re-enable auto-regime."""
        with self._lock:
            self._weights = dict(DEFAULT_WEIGHTS)
            self._active_preset = "default"
            self._regime_auto = True
            snapshot = (self._active_preset, dict(self._weights), self._regime_auto)
        if persist:
            self._persist(*snapshot)

    def hydrate(self) -> bool:
        """Load persisted overrides once. Returns True when a row was applied."""
        with self._lock:
            if self._hydrated:
                return False
            self._hydrated = True
        try:
            from app.scoring.weight_persist import load_overrides

            loaded = load_overrides()
        except Exception:
            return False
        if loaded is None:
            return False
        preset, weights, _regime = loaded
        self.apply(weights, preset_name=preset, persist=False)
        return True

    @staticmethod
    def _persist(
        preset: str, weights: dict[ScoringCategory, float], regime_auto: bool
    ) -> None:
        try:
            from app.scoring.weight_persist import save_overrides

            save_overrides(preset, weights, regime_auto)
        except Exception:
            return


_weight_config = WeightConfig()


def get_weight_config() -> WeightConfig:
    """Return the global weight configuration singleton."""
    return _weight_config


def hydrate_weight_config() -> None:
    """Startup hook — restore Apply after process restart."""
    _weight_config.hydrate()
