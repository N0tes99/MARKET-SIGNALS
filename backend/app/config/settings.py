"""Application configuration and settings."""

from pathlib import Path

from pydantic import field_validator
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
    # Social JWT (httpOnly cookie); keep SECRET_KEY strong in production
    access_token_expire_minutes: int = 60 * 24 * 14  # 14 days

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
    # Coinglass (liquidations) — empty key skips fetch; funding/OI still work
    coinglass_api_key: str = ""
    coinglass_base_url: str = "https://open-api-v4.coinglass.com"
    coinglass_exchange_list: str = "Binance,OKX,Bybit"

    # Product freshness gate (not TTL SWR): seconds since last successful
    # OHLCV/ticker fetch, and consecutive empty/error responses.
    market_data_stale_seconds: int = 900
    market_data_failure_threshold: int = 3

    # Learning store: auto (Postgres if reachable), postgres, or memory
    signal_store: str = "auto"

    # Alerts — Discord bot (preferred) / webhook fallback + SMTP email
    alert_enabled: bool = False
    alert_min_confidence: float = 65.0
    alert_min_grade: str = "B"
    alert_cooldown_minutes: int = 120
    alert_discord_bot_token: str = ""
    alert_discord_channel_id: str = ""
    alert_discord_webhook_url: str = ""
    alert_email_to: str = ""
    alert_email_from: str = ""
    alert_smtp_host: str = ""
    alert_smtp_port: int = 587
    alert_smtp_user: str = ""
    alert_smtp_password: str = ""
    alert_smtp_use_tls: bool = True

    # HTTP Basic Auth — empty password disables auth (local default)
    auth_username: str = "signal"
    auth_password: str = ""

    # Keep-warm / scheduled paper ticks (header X-Cron-Secret). Empty = cron-tick off.
    cron_secret: str = ""

    # Reddit social confirmation (public JSON). Disabled = F&G-only sentiment.
    reddit_social_enabled: bool = True
    reddit_user_agent: str = "signal-engine/1.0 (research bot; +https://github.com/N0tes99/MARKET-SIGNALS)"

    # Shared site TOTP (Authenticator) — empty secret disables the gate
    # Generate with: python -c "import pyotp; print(pyotp.random_base32())"
    site_totp_secret: str = ""
    site_totp_issuer: str = "Signal Engine"
    site_gate_expire_hours: int = 12

    # Comma-separated social usernames that may see Outcome log (TP / Hit / Miss)
    admin_usernames: str = "Admin"

    # Comma-separated browser origins (Netlify URL in production)
    cors_origins: str = "http://localhost:3000"
    # Public frontend URL for email verification links
    public_app_url: str = ""
    # Min seconds between verification email sends
    email_verify_cooldown_seconds: int = 60

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        """Accept postgres:// URLs and force asyncpg driver."""
        if not isinstance(value, str) or not value:
            return value
        url = value
        if url.startswith("postgres://"):
            url = "postgresql://" + url.removeprefix("postgres://")
        if url.startswith("postgresql://") and "+asyncpg" not in url and "+psycopg" not in url:
            url = "postgresql+asyncpg://" + url.removeprefix("postgresql://")
        return url

    def cors_origin_list(self) -> list[str]:
        """Parse CORS_ORIGINS into a list of origins."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def admin_username_set(self) -> set[str]:
        """Lowercased admin usernames allowed for private Outcome log."""
        return {
            name.strip().lower()
            for name in self.admin_usernames.split(",")
            if name.strip()
        }

    def is_admin_username(self, username: str) -> bool:
        """True when username is listed in ADMIN_USERNAMES (case-insensitive)."""
        return username.strip().lower() in self.admin_username_set()

    def resolved_public_app_url(self) -> str:
        """Frontend base URL for verification links."""
        if self.public_app_url.strip():
            return self.public_app_url.strip().rstrip("/")
        origins = self.cors_origin_list()
        if origins:
            return origins[0].rstrip("/")
        return "http://localhost:3000"


settings = Settings()
