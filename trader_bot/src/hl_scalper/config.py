from __future__ import annotations

from dataclasses import dataclass


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
    daily_loss_kill_pct: float = 0.02
    paper_equity_usd: float = 10_000.0
    taker_fee_bps: float = 3.5
    live_enabled: bool = False
    journal_path: str = "data/journal.jsonl"


DEFAULTS = Settings()
