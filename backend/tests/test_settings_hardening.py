"""Production settings refuse a default SECRET_KEY and force debug off."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config.settings import Settings


@pytest.fixture
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("APP_ENV", "APP_DEBUG", "SECRET_KEY"):
        monkeypatch.delenv(key, raising=False)


def test_development_keeps_insecure_defaults(isolated_env: None) -> None:
    loaded = Settings(_env_file=None, app_env="development")
    assert loaded.app_debug is True
    assert loaded.secret_key == "change-me-in-production"


def test_production_rejects_default_secret_key(isolated_env: None) -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(
            _env_file=None,
            app_env="production",
            secret_key="change-me-in-production",
        )


def test_production_rejects_blank_secret_key(isolated_env: None) -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(_env_file=None, app_env="production", secret_key="   ")


def test_production_forces_debug_off(isolated_env: None) -> None:
    loaded = Settings(
        _env_file=None,
        app_env="production",
        secret_key="unit-test-secret-key-not-default",
        app_debug=True,
    )
    assert loaded.app_debug is False
    assert loaded.secret_key == "unit-test-secret-key-not-default"
