"""Postgres-backed semantic stats."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.engines.learning_engine.postgres_store import to_sync_database_url
from app.memory.semantic.types import SemanticStat
from app.models.cortex_memory import CortexSemanticStatModel

logger = logging.getLogger(__name__)


def _row_to_stat(row: CortexSemanticStatModel) -> SemanticStat:
    return SemanticStat(
        metric=row.metric,
        signal=row.signal,
        score_bucket=row.score_bucket,
        sample_count=row.sample_count,
        median_hours=row.median_hours,
        hit_rate=row.hit_rate,
        payload=dict(row.payload or {}),
        updated_at=row.updated_at,
    )


class PostgresSemanticStore:
    """Persist consolidated lead-time / calibration stats."""

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
            logger.warning("Postgres semantic store ping failed: %s", exc)
            return False

    def tables_ready(self) -> bool:
        try:
            return inspect(self._engine).has_table("cortex_semantic_stats")
        except Exception:
            return False

    def upsert(self, stat: SemanticStat) -> None:
        now = datetime.now(UTC)
        values = {
            "id": uuid4(),
            "metric": stat.metric,
            "signal": stat.signal,
            "score_bucket": stat.score_bucket,
            "sample_count": stat.sample_count,
            "median_hours": stat.median_hours,
            "hit_rate": stat.hit_rate,
            "payload": dict(stat.payload),
            "updated_at": now,
        }
        with self._lock, self._session_factory() as session:
            stmt = pg_insert(CortexSemanticStatModel).values(**values)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_cortex_semantic_metric_signal_bucket",
                set_={
                    "sample_count": stmt.excluded.sample_count,
                    "median_hours": stmt.excluded.median_hours,
                    "hit_rate": stmt.excluded.hit_rate,
                    "payload": stmt.excluded.payload,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            session.execute(stmt)
            session.commit()

    def get(self, metric: str, signal: str, *, score_bucket: int = -1) -> SemanticStat | None:
        with self._session_factory() as session:
            row = session.scalars(
                select(CortexSemanticStatModel).where(
                    CortexSemanticStatModel.metric == metric,
                    CortexSemanticStatModel.signal == signal,
                    CortexSemanticStatModel.score_bucket == score_bucket,
                )
            ).first()
            return _row_to_stat(row) if row is not None else None

    def all_stats(self) -> list[SemanticStat]:
        with self._session_factory() as session:
            rows = session.scalars(select(CortexSemanticStatModel)).all()
            return [_row_to_stat(row) for row in rows]
