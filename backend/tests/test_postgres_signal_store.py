"""Postgres signal store tests (skipped when DB is unavailable)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.config import settings
from app.engines.learning_engine.postgres_store import PostgresSignalStore, to_sync_database_url
from app.engines.learning_engine.types import SignalRecord


def _store_or_skip() -> PostgresSignalStore:
    store = PostgresSignalStore(settings.database_url)
    if not store.ping():
        pytest.skip("Postgres not available")
    return store


def test_to_sync_database_url() -> None:
    assert "+psycopg" in to_sync_database_url(
        "postgresql+asyncpg://user:pass@localhost:5432/db"
    )


def test_postgres_roundtrip_outcome() -> None:
    store = _store_or_skip()
    record = SignalRecord(
        id=uuid4(),
        symbol="SPY",
        timestamp=datetime.now(UTC),
        confidence=68.0,
        trade_grade="B",
        trade_state="WATCH",
        execution_signal="WATCH",
        opportunity_score=68.0,
        category_scores={"Trend": 70.0},
        expected_value=0.5,
        entry_price=500.0,
        stop_loss=495.0,
        take_profit=505.0,
    )
    store.add(record)
    fetched = store.get(record.id)
    assert fetched is not None
    assert fetched.symbol == "SPY"
    assert fetched.confidence == 68.0

    record.outcome = "win"
    record.realized_return_pct = 0.4
    record.resolved_at = datetime.now(UTC)
    updated = store.update(record)
    assert updated is not None
    assert updated.outcome == "win"
    assert store.count("SPY") >= 1
