"""Application configuration and settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root .env (signal-engine/.env) — works when running from backend/
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILES = (PROJECT_ROOT / ".env", Path(".env"))


class Settings(BaseSettings):
    """Central application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=[str(f) for f in ENV_FILES if f.exists()] or ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    app_name: str = "Signal Engine"
    app_env: str = "development"
    app_debug: bool = True
    api_v1_prefix: str = "/api/v1"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    secret_key: str = "change-me-in-production"

    postgres_user: str = "signal_engine"
    postgres_password: str = "signal_engine"
    postgres_db: str = "signal_engine"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: str = (
        "postgresql+asyncpg://signal_engine:signal_engine@localhost:5432/signal_engine"
    )

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_url: str = "redis://localhost:6379/0"

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    openai_api_key: str = ""

    binance_spot_url: str = "https://api.binance.com"
    binance_futures_url: str = "https://fapi.binance.com"
    kraken_api_url: str = "https://api.kraken.com"
    fred_api_key: str = ""


settings = Settings()
