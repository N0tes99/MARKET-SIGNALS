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


def test_production_rejects_blank_auth_password(isolated_env: None) -> None:
    with pytest.raises(ValidationError, match="AUTH_PASSWORD"):
        Settings(
            _env_file=None,
            app_env="production",
            secret_key="unit-test-secret-key-not-default",
            auth_password="",
            site_totp_secret="JBSWY3DPEHPK3PXP",
        )


def test_production_rejects_blank_totp_secret(isolated_env: None) -> None:
    with pytest.raises(ValidationError, match="SITE_TOTP_SECRET"):
        Settings(
            _env_file=None,
            app_env="production",
            secret_key="unit-test-secret-key-not-default",
            auth_password="unit-test-auth-password",
            site_totp_secret="",
        )


def test_production_forces_debug_off(isolated_env: None) -> None:
    loaded = Settings(
        _env_file=None,
        app_env="production",
        secret_key="unit-test-secret-key-not-default",
        auth_password="unit-test-auth-password",
        site_totp_secret="JBSWY3DPEHPK3PXP",
        app_debug=True,
    )
    assert loaded.app_debug is False
    assert loaded.secret_key == "unit-test-secret-key-not-default"


def test_development_cors_includes_local_next_ports(
    isolated_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    loaded = Settings(_env_file=None, app_env="development", cors_origins="http://localhost:3000")
    origins = loaded.cors_origin_list()
    assert "http://localhost:3000" in origins
    assert "http://localhost:3001" in origins
    assert "http://127.0.0.1:3000" in origins
    assert "http://127.0.0.1:3001" in origins


def test_production_cors_does_not_inject_local_ports(
    isolated_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    loaded = Settings(
        _env_file=None,
        app_env="production",
        secret_key="unit-test-secret-key-not-default",
        auth_password="unit-test-auth-password",
        site_totp_secret="JBSWY3DPEHPK3PXP",
        cors_origins="https://example.netlify.app",
    )
    assert loaded.cors_origin_list() == ["https://example.netlify.app"]
