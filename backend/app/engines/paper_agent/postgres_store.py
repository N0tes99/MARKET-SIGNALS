"""Postgres-backed paper trade store — PnL survives process restarts."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from threading import Lock
from uuid import UUID

from sqlalchemy import create_engine, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.engines.learning_engine.postgres_store import to_sync_database_url
from app.engines.paper_agent.types import PaperTrade
from app.models.paper_trade import PaperAgentStateModel, PaperTradeModel

logger = logging.getLogger(__name__)


def _to_uuid(value: str) -> UUID:
    return UUID(str(value))


def _row_to_trade(row: PaperTradeModel) -> PaperTrade:
    return PaperTrade(
        id=str(row.id),
        symbol=row.symbol,
        source=row.source,  # type: ignore[arg-type]
        setup_type=row.setup_type,
        direction=row.direction,  # type: ignore[arg-type]
        fingerprint=row.fingerprint,
        signal_at=row.signal_at,
        confidence=row.confidence,
        opportunity_score=row.opportunity_score,
        size_usd=row.size_usd,
        status=row.status,  # type: ignore[arg-type]
        optimistic_entry=row.optimistic_entry,
        optimistic_entry_at=row.optimistic_entry_at,
        optimistic_exit=row.optimistic_exit,
        optimistic_pnl_usd=row.optimistic_pnl_usd,
        optimistic_return_pct=row.optimistic_return_pct,
        honest_entry=row.honest_entry,
        honest_entry_at=row.honest_entry_at,
        honest_bar_ts=row.honest_bar_ts,
        honest_exit=row.honest_exit,
        honest_pnl_usd=row.honest_pnl_usd,
        honest_return_pct=row.honest_return_pct,
        mark_price=row.mark_price,
        closed_at=row.closed_at,
        close_reason=row.close_reason,
        factors=list(row.factors or []),
        notes=row.notes or "",
    )


def _trade_values(trade: PaperTrade) -> dict:
    return {
        "id": _to_uuid(trade.id),
        "symbol": trade.symbol.upper(),
        "source": trade.source,
        "setup_type": trade.setup_type,
        "direction": trade.direction,
        "fingerprint": trade.fingerprint,
        "signal_at": trade.signal_at,
        "confidence": trade.confidence,
        "opportunity_score": trade.opportunity_score,
        "size_usd": trade.size_usd,
        "status": trade.status,
        "optimistic_entry": trade.optimistic_entry,
        "optimistic_entry_at": trade.optimistic_entry_at,
        "optimistic_exit": trade.optimistic_exit,
        "optimistic_pnl_usd": trade.optimistic_pnl_usd,
        "optimistic_return_pct": trade.optimistic_return_pct,
        "honest_entry": trade.honest_entry,
        "honest_entry_at": trade.honest_entry_at,
        "honest_bar_ts": trade.honest_bar_ts,
        "honest_exit": trade.honest_exit,
        "honest_pnl_usd": trade.honest_pnl_usd,
        "honest_return_pct": trade.honest_return_pct,
        "mark_price": trade.mark_price,
        "closed_at": trade.closed_at,
        "close_reason": trade.close_reason,
        "factors": list(trade.factors),
        "notes": trade.notes,
        "updated_at": datetime.now(UTC),
    }


class PostgresPaperTradeStore:
    """Persist paper trades so public PnL survives restarts."""

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
            logger.warning("Postgres paper store ping failed: %s", exc)
            return False

    def upsert(self, trade: PaperTrade) -> None:
        values = _trade_values(trade)
        stmt = pg_insert(PaperTradeModel).values(**values)
        update_cols = {k: stmt.excluded[k] for k in values if k != "id"}
        stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=update_cols)
        with self._lock, self._session_factory() as session:
            session.execute(stmt)
            session.commit()

    def get(self, trade_id: str) -> PaperTrade | None:
        with self._lock, self._session_factory() as session:
            row = session.get(PaperTradeModel, _to_uuid(trade_id))
            return _row_to_trade(row) if row else None

    def list_all(self) -> list[PaperTrade]:
        with self._lock, self._session_factory() as session:
            rows = session.scalars(select(PaperTradeModel)).all()
            return [_row_to_trade(r) for r in rows]

    def open_or_pending(self) -> list[PaperTrade]:
        with self._lock, self._session_factory() as session:
            rows = session.scalars(
                select(PaperTradeModel).where(
                    PaperTradeModel.status.in_(("pending_honest", "open", "closing"))
                )
            ).all()
            return [_row_to_trade(r) for r in rows]

    def fingerprints_active(self) -> set[str]:
        with self._lock, self._session_factory() as session:
            rows = session.scalars(
                select(PaperTradeModel.fingerprint).where(
                    PaperTradeModel.status.in_(("pending_honest", "open", "closing"))
                )
            ).all()
            return set(rows)

    def set_meta(self, key: str, value: str) -> None:
        now = datetime.now(UTC)
        stmt = pg_insert(PaperAgentStateModel).values(
            key=key,
            value=value,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["key"],
            set_={"value": value, "updated_at": now},
        )
        with self._lock, self._session_factory() as session:
            session.execute(stmt)
            session.commit()

    def get_meta(self, key: str) -> str | None:
        with self._lock, self._session_factory() as session:
            row = session.get(PaperAgentStateModel, key)
            return row.value if row else None

    def clear_all(self) -> int:
        """Wipe all paper trades + agent meta. Returns trades deleted."""
        with self._lock, self._session_factory() as session:
            count = len(session.scalars(select(PaperTradeModel.id)).all())
            session.execute(delete(PaperTradeModel))
            session.execute(delete(PaperAgentStateModel))
            session.commit()
            return count
