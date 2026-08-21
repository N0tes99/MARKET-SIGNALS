"""Factory for cortex episodic stores."""

from __future__ import annotations

import logging

from app.config import settings
from app.memory.episodic.postgres import PostgresEpisodicStore
from app.memory.episodic.store import EpisodicStore, InMemoryEpisodicStore

logger = logging.getLogger(__name__)


def build_episodic_store(*, prefer_postgres: bool | None = None) -> EpisodicStore:
    """Postgres when reachable and migrated; otherwise in-memory ring buffer."""
    mode = settings.signal_store.lower().strip()
    if prefer_postgres is False or mode == "memory":
        logger.info("Using in-memory cortex episodic store")
        return InMemoryEpisodicStore(max_records=200)

    if mode not in {"auto", "postgres", "postgresql"} and prefer_postgres is not True:
        return InMemoryEpisodicStore(max_records=200)

    try:
        store = PostgresEpisodicStore(settings.database_url)
        if store.ping() and store.tables_ready():
            logger.info("Using Postgres cortex episodic store (%s)", mode)
            return store
        logger.warning(
            "Postgres episodic table missing or unreachable — using in-memory cortex store"
        )
    except Exception:
        logger.exception("Failed to init Postgres episodic store — using memory")

    return InMemoryEpisodicStore(max_records=200)
