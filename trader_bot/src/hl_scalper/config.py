from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Lab defaults. Live stays off until dual-control arming + allow_live_orders."""

    info_url: str = "https://api.hyperliquid.xyz/info"
    ws_url: str = "wss://api.hyperliquid.xyz/ws"
    coins: tuple[str, ...] = ("BTC", "ETH", "SOL", "HYPE")
    imbalance_min: float = 0.72
    spread_bps_max: float = 12.0
    min_notional: float = 50_000.0
    book_levels: int = 5
    poll_interval_s: float = 1.0
    max_book_age_s: float = 15.0
    max_ws_book_age_s: float = 2.0
    use_ws: bool = True
    max_concurrent_positions: int = 1
    max_notional_usd: float = 100.0
    daily_loss_kill_pct: float = 0.01
    weekly_loss_kill_pct: float = 0.03
    max_leverage: float = 2.0
    max_consecutive_losses: int = 5
    cooldown_seconds: float = 1800.0
    paper_equity_usd: float = 10_000.0
    taker_fee_bps: float = 3.5
    fee_edge_buffer_bps: float = 2.0
    hold_seconds: float = 5.0
    adverse_exit_bps: float = 8.0
    max_feed_failures: int = 10
    live_enabled: bool = False
    allow_live_orders: bool = False  # must be explicitly enabled
    dry_run_live: bool = True  # even when armed, default is dry-run (no /exchange post)
    live_coins: tuple[str, ...] = ("BTC", "ETH")
    data_dir: str = "data"
    journal_path: str = "data/journal.jsonl"
    heartbeat_path: str = "data/heartbeat.json"
    books_path: str = "data/books.jsonl"
    arm_file: str = "data/ARMED"
    record_books: bool = False
    reconcile_each_entry: bool = True
    # Multi-agent desk
    ensemble: bool = False
    ensemble_min_agree: int = 2
    funding_extreme: float = 0.0001
    spread_micro_tight_bps: float = 4.0

    @classmethod
    def from_env(cls, **overrides: object) -> Settings:
        base = cls(
            live_enabled=_env_bool("LIVE_ENABLED", False),
            allow_live_orders=_env_bool("ALLOW_LIVE_ORDERS", False),
            dry_run_live=_env_bool("DRY_RUN_LIVE", True),
            use_ws=_env_bool("HL_USE_WS", True),
            ensemble=_env_bool("HL_ENSEMBLE", False),
        )
        if not overrides:
            return base
        data = {**base.__dict__, **overrides}
        return cls(**data)  # type: ignore[arg-type]

    def ensure_data_dirs(self) -> None:
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.journal_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.heartbeat_path).parent.mkdir(parents=True, exist_ok=True)


DEFAULTS = Settings()
