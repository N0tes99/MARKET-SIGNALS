"""Factory for paper trade stores."""

from __future__ import annotations

import logging
from typing import Protocol

from app.config import settings
from app.engines.paper_agent.postgres_store import PostgresPaperTradeStore
from app.engines.paper_agent.store import PaperTradeStore
from app.engines.paper_agent.types import PaperTrade

logger = logging.getLogger(__name__)


class PaperStoreProtocol(Protocol):
    def upsert(self, trade: PaperTrade) -> None: ...
    def get(self, trade_id: str) -> PaperTrade | None: ...
    def list_all(self) -> list[PaperTrade]: ...
    def open_or_pending(self) -> list[PaperTrade]: ...
    def fingerprints_active(self) -> set[str]: ...


def build_paper_store() -> PaperStoreProtocol:
    """Prefer Postgres so public PnL never dies across restarts."""
    mode = settings.signal_store.lower().strip()
    if mode == "memory":
        logger.info("Using in-memory paper store (SIGNAL_STORE=memory)")
        return PaperTradeStore()

    try:
        store = PostgresPaperTradeStore(settings.database_url)
        if store.ping():
            logger.info("Using Postgres paper store")
            return store
        logger.warning("Postgres unreachable — paper store falling back to memory")
    except Exception:
        logger.exception("Failed to init Postgres paper store — using memory")

    return PaperTradeStore()
