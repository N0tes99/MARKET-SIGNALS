from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Lab defaults. Live stays off."""

    info_url: str = "https://api.hyperliquid.xyz/info"
    coins: tuple[str, ...] = ("BTC", "ETH", "SOL", "HYPE")
    imbalance_min: float = 0.72
    spread_bps_max: float = 12.0
    min_notional: float = 50_000.0
    book_levels: int = 5
    poll_interval_s: float = 1.0
    max_book_age_s: float = 15.0
    max_concurrent_positions: int = 1
    max_notional_usd: float = 100.0
    # Capital-preservation defaults (see docs/risk-policy.md).
    daily_loss_kill_pct: float = 0.01  # −1% day → kill
    weekly_loss_kill_pct: float = 0.03
    max_leverage: float = 2.0
    max_consecutive_losses: int = 5
    cooldown_seconds: float = 1800.0
    paper_equity_usd: float = 10_000.0
    taker_fee_bps: float = 3.5
    fee_edge_buffer_bps: float = 2.0  # edge must clear fees + buffer
    hold_seconds: float = 5.0
    max_feed_failures: int = 10
    live_enabled: bool = False
    live_coins: tuple[str, ...] = ("BTC", "ETH")  # dust live universe
    data_dir: str = "data"
    journal_path: str = "data/journal.jsonl"
    heartbeat_path: str = "data/heartbeat.json"
    books_path: str = "data/books.jsonl"
    record_books: bool = False

    def ensure_data_dirs(self) -> None:
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.journal_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.heartbeat_path).parent.mkdir(parents=True, exist_ok=True)


DEFAULTS = Settings()
