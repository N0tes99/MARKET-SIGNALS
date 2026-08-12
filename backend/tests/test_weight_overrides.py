"""Weight Apply persists; hydrate restores after a fresh singleton."""

from app.scoring.presets import WEIGHT_PRESETS
from app.scoring.weight_config import WeightConfig
from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory


def test_apply_persists(monkeypatch) -> None:
    saved: dict = {}

    def fake_save(preset, weights, regime_auto):
        saved["preset"] = preset
        saved["weights"] = dict(weights)
        saved["regime_auto"] = regime_auto

    monkeypatch.setattr("app.scoring.weight_persist.save_overrides", fake_save)
    cfg = WeightConfig()
    cfg.apply(WEIGHT_PRESETS["momentum_focused"], preset_name="momentum_focused")
    assert saved["preset"] == "momentum_focused"
    assert saved["regime_auto"] is False
    assert saved["weights"][ScoringCategory.MOMENTUM] > DEFAULT_WEIGHTS[ScoringCategory.MOMENTUM]


def test_hydrate_restores_apply(monkeypatch) -> None:
    weights = dict(WEIGHT_PRESETS["momentum_focused"])
    monkeypatch.setattr(
        "app.scoring.weight_persist.load_overrides",
        lambda: ("momentum_focused", weights, False),
    )
    cfg = WeightConfig()
    assert cfg.hydrate() is True
    assert cfg.get_preset_name() == "momentum_focused"
    assert cfg.is_regime_auto() is False
    assert cfg.hydrate() is False


def test_reset_persists_default(monkeypatch) -> None:
    saved: dict = {}

    def fake_save(preset, weights, regime_auto):
        saved["preset"] = preset
        saved["regime_auto"] = regime_auto

    monkeypatch.setattr("app.scoring.weight_persist.save_overrides", fake_save)
    cfg = WeightConfig()
    cfg.apply(WEIGHT_PRESETS["momentum_focused"], preset_name="momentum_focused", persist=False)
    cfg.reset()
    assert saved["preset"] == "default"
    assert saved["regime_auto"] is True
