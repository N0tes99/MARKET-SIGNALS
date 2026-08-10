"""Durable alert state store (Postgres) + in-memory fallback."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock

from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.engines.learning_engine.postgres_store import to_sync_database_url
from app.models.alert_state import AlertStateModel

logger = logging.getLogger(__name__)


@dataclass
class AlertSnapshot:
    """Last alerted inputs for a symbol (durable)."""

    confidence: float
    trade_grade: str
    trend: str
    trade_state: str
    execution_signal: str
    expected_value: float
    at: datetime


class MemoryAlertStateStore:
    """Process-local alert state (tests / DB down)."""

    backend = "memory"

    def __init__(self) -> None:
        self._lock = Lock()
        self._last_sent: dict[str, datetime] = {}
        self._last_alerted: dict[str, AlertSnapshot] = {}

    def load(self) -> tuple[dict[str, datetime], dict[str, AlertSnapshot]]:
        with self._lock:
            return dict(self._last_sent), dict(self._last_alerted)

    def save_sent(self, symbol: str, sent_at: datetime, snapshot: AlertSnapshot | None) -> None:
        key = symbol.upper()
        with self._lock:
            self._last_sent[key] = sent_at
            if snapshot is not None:
                self._last_alerted[key] = snapshot

    def touch_cooldown(self, symbol: str, sent_at: datetime) -> None:
        key = symbol.upper()
        with self._lock:
            self._last_sent[key] = sent_at


class PostgresAlertStateStore:
    """Persist alert cooldowns + last snapshots across restarts."""

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
            logger.warning("Postgres alert state ping failed: %s", exc)
            return False

    def load(self) -> tuple[dict[str, datetime], dict[str, AlertSnapshot]]:
        last_sent: dict[str, datetime] = {}
        last_alerted: dict[str, AlertSnapshot] = {}
        with self._lock, self._session_factory() as session:
            rows = session.scalars(select(AlertStateModel)).all()
            for row in rows:
                key = row.symbol.upper()
                last_sent[key] = row.last_sent_at
                last_alerted[key] = AlertSnapshot(
                    confidence=row.confidence,
                    trade_grade=row.trade_grade,
                    trend=row.trend,
                    trade_state=row.trade_state,
                    execution_signal=row.execution_signal,
                    expected_value=row.expected_value,
                    at=row.updated_at or row.last_sent_at,
                )
        return last_sent, last_alerted

    def save_sent(self, symbol: str, sent_at: datetime, snapshot: AlertSnapshot | None) -> None:
        key = symbol.upper()
        now = datetime.now(UTC)
        if snapshot is None:
            with self._lock, self._session_factory() as session:
                row = session.get(AlertStateModel, key)
                if row is None:
                    session.add(
                        AlertStateModel(
                            symbol=key,
                            last_sent_at=sent_at,
                            confidence=0.0,
                            trade_grade="F",
                            trend="Neutral",
                            trade_state="IGNORE",
                            execution_signal="WAIT",
                            expected_value=0.0,
                            updated_at=now,
                        )
                    )
                else:
                    row.last_sent_at = sent_at
                    row.updated_at = now
                session.commit()
            return

        values = {
            "symbol": key,
            "last_sent_at": sent_at,
            "confidence": snapshot.confidence,
            "trade_grade": snapshot.trade_grade,
            "trend": snapshot.trend,
            "trade_state": snapshot.trade_state,
            "execution_signal": snapshot.execution_signal,
            "expected_value": snapshot.expected_value,
            "updated_at": now,
        }
        stmt = pg_insert(AlertStateModel).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol"],
            set_={k: stmt.excluded[k] for k in values if k != "symbol"},
        )
        with self._lock, self._session_factory() as session:
            session.execute(stmt)
            session.commit()

    def touch_cooldown(self, symbol: str, sent_at: datetime) -> None:
        self.save_sent(symbol, sent_at, None)


def build_alert_state_store() -> MemoryAlertStateStore | PostgresAlertStateStore:
    """Prefer Postgres so Discord cooldowns survive restarts."""
    mode = settings.signal_store.lower().strip()
    if mode == "memory":
        logger.info("Using in-memory alert state (SIGNAL_STORE=memory)")
        return MemoryAlertStateStore()

    try:
        store = PostgresAlertStateStore(settings.database_url)
        if store.ping():
            logger.info("Using Postgres alert state store")
            return store
        logger.warning("Postgres unreachable — alert state falling back to memory")
    except Exception:
        logger.exception("Failed to init Postgres alert state — using memory")

    return MemoryAlertStateStore()
