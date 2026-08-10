"""In-memory paper trade store (process-local; Postgres optional later)."""

from __future__ import annotations

from threading import Lock

from app.engines.paper_agent.types import PaperTrade


class PaperTradeStore:
    """Thread-safe in-memory store for the public paper agent."""

    backend = "memory"

    def __init__(self) -> None:
        self._lock = Lock()
        self._trades: dict[str, PaperTrade] = {}
        self._meta: dict[str, str] = {}

    def upsert(self, trade: PaperTrade) -> None:
        with self._lock:
            self._trades[trade.id] = trade

    def get(self, trade_id: str) -> PaperTrade | None:
        with self._lock:
            return self._trades.get(trade_id)

    def list_all(self) -> list[PaperTrade]:
        with self._lock:
            return list(self._trades.values())

    def open_or_pending(self) -> list[PaperTrade]:
        with self._lock:
            return [t for t in self._trades.values() if t.status in {"pending_honest", "open"}]

    def fingerprints_active(self) -> set[str]:
        with self._lock:
            return {
                t.fingerprint
                for t in self._trades.values()
                if t.status in {"pending_honest", "open"}
            }

    def set_meta(self, key: str, value: str) -> None:
        with self._lock:
            self._meta[key] = value

    def get_meta(self, key: str) -> str | None:
        with self._lock:
            return self._meta.get(key)
