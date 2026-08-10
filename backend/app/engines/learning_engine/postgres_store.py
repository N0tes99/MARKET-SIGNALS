"""Postgres-backed signal store (sync SQLAlchemy for learning engine)."""

from __future__ import annotations

import logging
from threading import Lock
from uuid import UUID

from sqlalchemy import create_engine, desc, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.engines.learning_engine.types import SignalRecord
from app.models.signal_record import SignalRecordModel

logger = logging.getLogger(__name__)


def to_sync_database_url(async_url: str) -> str:
    """Convert asyncpg URL to psycopg sync URL."""
    if "+asyncpg" in async_url:
        return async_url.replace("+asyncpg", "+psycopg", 1)
    if async_url.startswith("postgresql://"):
        return async_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return async_url


def _row_to_record(row: SignalRecordModel) -> SignalRecord:
    return SignalRecord(
        id=row.id,
        symbol=row.symbol,
        timestamp=row.timestamp,
        confidence=row.confidence,
        trade_grade=row.trade_grade,
        trade_state=row.trade_state,
        execution_signal=row.execution_signal,
        opportunity_score=row.opportunity_score,
        category_scores=dict(row.category_scores or {}),
        expected_value=row.expected_value,
        entry_price=row.entry_price,
        stop_loss=row.stop_loss,
        take_profit=row.take_profit,
        outcome=row.outcome,
        realized_return_pct=row.realized_return_pct,
        notes=row.notes,
        resolved_at=row.resolved_at,
    )


class PostgresSignalStore:
    """Persist signal records in PostgreSQL."""

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
        """Return True if the database accepts connections."""
        try:
            with self._engine.connect() as conn:
                conn.execute(select(1))
            return True
        except Exception as exc:
            logger.warning("Postgres signal store ping failed: %s", exc)
            return False

    def add(self, record: SignalRecord) -> None:
        """Insert a new signal record."""
        with self._lock, self._session_factory() as session:
            session.add(
                SignalRecordModel(
                    id=record.id,
                    symbol=record.symbol.upper(),
                    timestamp=record.timestamp,
                    confidence=record.confidence,
                    trade_grade=record.trade_grade,
                    trade_state=record.trade_state,
                    execution_signal=record.execution_signal,
                    opportunity_score=record.opportunity_score,
                    category_scores=record.category_scores,
                    expected_value=record.expected_value,
                    entry_price=record.entry_price,
                    stop_loss=record.stop_loss,
                    take_profit=record.take_profit,
                    outcome=record.outcome,
                    realized_return_pct=record.realized_return_pct,
                    notes=record.notes,
                    resolved_at=record.resolved_at,
                )
            )
            session.commit()

    def list_for_symbol(self, symbol: str, limit: int = 50) -> list[SignalRecord]:
        """Return recent records for a symbol, newest first."""
        with self._session_factory() as session:
            rows = session.scalars(
                select(SignalRecordModel)
                .where(SignalRecordModel.symbol == symbol.upper())
                .order_by(desc(SignalRecordModel.timestamp))
                .limit(limit)
            ).all()
            return [_row_to_record(row) for row in rows]

    def list_all(self, limit: int = 100) -> list[SignalRecord]:
        """Return recent records across all symbols, newest first."""
        with self._session_factory() as session:
            rows = session.scalars(
                select(SignalRecordModel)
                .order_by(desc(SignalRecordModel.timestamp))
                .limit(limit)
            ).all()
            return [_row_to_record(row) for row in rows]

    def get(self, record_id: UUID) -> SignalRecord | None:
        """Find a record by ID."""
        with self._session_factory() as session:
            row = session.get(SignalRecordModel, record_id)
            return _row_to_record(row) if row else None

    def update(self, record: SignalRecord) -> SignalRecord | None:
        """Update outcome fields for an existing record."""
        with self._lock, self._session_factory() as session:
            row = session.get(SignalRecordModel, record.id)
            if row is None:
                return None
            row.outcome = record.outcome
            row.realized_return_pct = record.realized_return_pct
            row.notes = record.notes
            row.resolved_at = record.resolved_at
            row.expected_value = record.expected_value
            row.entry_price = record.entry_price
            row.stop_loss = record.stop_loss
            row.take_profit = record.take_profit
            session.commit()
            session.refresh(row)
            return _row_to_record(row)

    def count(self, symbol: str | None = None) -> int:
        """Count stored records."""
        with self._session_factory() as session:
            stmt = select(func.count()).select_from(SignalRecordModel)
            if symbol:
                stmt = stmt.where(SignalRecordModel.symbol == symbol.upper())
            return int(session.scalar(stmt) or 0)
