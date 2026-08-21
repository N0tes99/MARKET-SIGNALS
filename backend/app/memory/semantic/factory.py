"""Factory for semantic memory stores."""

from __future__ import annotations

import logging

from app.config import settings
from app.memory.semantic.postgres import PostgresSemanticStore
from app.memory.semantic.store import InMemorySemanticStore, SemanticStore

logger = logging.getLogger(__name__)


def build_semantic_store(*, prefer_postgres: bool | None = None) -> SemanticStore:
    """Postgres when migrated; otherwise process-local stats."""
    mode = settings.signal_store.lower().strip()
    if prefer_postgres is False or mode == "memory":
        return InMemorySemanticStore()

    if mode not in {"auto", "postgres", "postgresql"} and prefer_postgres is not True:
        return InMemorySemanticStore()

    try:
        store = PostgresSemanticStore(settings.database_url)
        if store.ping() and store.tables_ready():
            logger.info("Using Postgres cortex semantic store (%s)", mode)
            return store
        logger.warning("Postgres semantic table missing — using in-memory stats")
    except Exception:
        logger.exception("Failed to init Postgres semantic store — using memory")

    return InMemorySemanticStore()
