"""Postgres-backed cortex episodic store."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from threading import Lock

from sqlalchemy import create_engine, desc, func, inspect, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.cortex.types import WorkingMemory
from app.engines.learning_engine.postgres_store import to_sync_database_url
from app.memory.episodic.store import serialize_working_memory
from app.memory.episodic.types import EpisodicRecord
from app.models.cortex_memory import CortexEpisodeModel

logger = logging.getLogger(__name__)


def _row_to_record(row: CortexEpisodeModel) -> EpisodicRecord:
    as_of = row.as_of
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=UTC)
    return EpisodicRecord(tick_id=row.tick_id, as_of=as_of, payload=dict(row.payload or {}))


class PostgresEpisodicStore:
    """Persist cortex ticks so working memory survives process restarts."""

    backend = "postgres"

    def __init__(self, database_url: str) -> None:
        sync_url = to_sync_database_url(database_url)
        self._engine: Engine = create_engine(
            sync_url,
            pool_pre_ping=True,
            pool_timeout=5,
            connect_args={"connect_timeout": 3},
        )
        self._session_factory = sessionmaker(self._engine, expire_on_commit=False)
        self._lock = Lock()

    def ping(self) -> bool:
        try:
            with self._engine.connect() as conn:
                conn.execute(select(1))
            return True
        except Exception as exc:
            logger.warning("Postgres episodic store ping failed: %s", exc)
            return False

    def tables_ready(self) -> bool:
        try:
            return inspect(self._engine).has_table("cortex_episodes")
        except Exception:
            logger.warning("Could not inspect cortex_episodes table", exc_info=True)
            return False

    def append(self, memory: WorkingMemory) -> EpisodicRecord:
        payload = serialize_working_memory(memory)
        values = {
            "tick_id": memory.tick_id,
            "as_of": memory.as_of,
            "payload": payload,
            "primed": memory.primed_symbols(),
            "triggering": memory.triggering_symbols(),
            "phase": memory.phase,
            "created_at": datetime.now(UTC),
        }
        with self._lock, self._session_factory() as session:
            stmt = pg_insert(CortexEpisodeModel).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=[CortexEpisodeModel.tick_id],
                set_={
                    "as_of": stmt.excluded.as_of,
                    "payload": stmt.excluded.payload,
                    "primed": stmt.excluded.primed,
                    "triggering": stmt.excluded.triggering,
                    "phase": stmt.excluded.phase,
                },
            )
            session.execute(stmt)
            session.commit()
        return EpisodicRecord(tick_id=memory.tick_id, as_of=memory.as_of, payload=payload)

    def latest(self) -> EpisodicRecord | None:
        with self._session_factory() as session:
            row = session.scalars(
                select(CortexEpisodeModel).order_by(desc(CortexEpisodeModel.as_of)).limit(1)
            ).first()
            return _row_to_record(row) if row is not None else None

    def history(self, limit: int = 20) -> list[EpisodicRecord]:
        n = max(1, min(limit, 500))
        with self._session_factory() as session:
            rows = session.scalars(
                select(CortexEpisodeModel)
                .order_by(desc(CortexEpisodeModel.as_of))
                .limit(n)
            ).all()
            records = [_row_to_record(row) for row in rows]
        records.reverse()
        return records

    def count(self) -> int:
        with self._session_factory() as session:
            return int(session.scalar(select(func.count()).select_from(CortexEpisodeModel)) or 0)
