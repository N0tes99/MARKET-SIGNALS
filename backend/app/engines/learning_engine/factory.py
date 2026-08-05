"""Factory for learning-engine signal stores."""

from __future__ import annotations

import logging

from app.config import settings
from app.engines.learning_engine.postgres_store import PostgresSignalStore
from app.engines.learning_engine.store import InMemorySignalStore, SignalStore

logger = logging.getLogger(__name__)


def build_signal_store(*, prefer_postgres: bool | None = None) -> SignalStore:
    """Build Postgres store when available; otherwise fall back to memory.

    ``SIGNAL_STORE`` env:
    - ``auto`` (default): Postgres if reachable, else memory
    - ``postgres``: require Postgres (still falls back with warning if down)
    - ``memory``: force in-memory
    """
    mode = settings.signal_store.lower().strip()
    if prefer_postgres is False or mode == "memory":
        logger.info("Using in-memory signal store")
        return InMemorySignalStore()

    if mode not in {"auto", "postgres", "postgresql"} and prefer_postgres is not True:
        return InMemorySignalStore()

    try:
        store = PostgresSignalStore(settings.database_url)
        if store.ping():
            logger.info("Using Postgres signal store (%s)", mode)
            return store
        logger.warning("Postgres unreachable — falling back to in-memory signal store")
    except Exception:
        logger.exception("Failed to init Postgres signal store — using memory")

    return InMemorySignalStore()
