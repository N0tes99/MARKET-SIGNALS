"""Load/save scoring weight overrides from Postgres (fail-open)."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from threading import Lock

from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.engines.learning_engine.postgres_store import to_sync_database_url
from app.models.weight_override import WeightOverrideModel
from app.scoring.weights import ScoringCategory, validate_weights

logger = logging.getLogger(__name__)

ROW_ID = 1
_lock = Lock()
_engine = None
_Session = None


def _session_factory():
    global _engine, _Session
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    if settings.signal_store.lower().strip() == "memory":
        return None
    with _lock:
        if _Session is not None:
            return _Session
        url = to_sync_database_url(settings.database_url)
        _engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_timeout=3,
            connect_args={"connect_timeout": 2},
        )
        _Session = sessionmaker(bind=_engine, expire_on_commit=False)
        return _Session


def load_overrides() -> tuple[str, dict[ScoringCategory, float], bool] | None:
    """Return (preset, weights, regime_auto) or None when unset / unreachable."""
    try:
        Session = _session_factory()
        if Session is None:
            return None
        with Session() as session:
            row = session.execute(
                select(WeightOverrideModel).where(WeightOverrideModel.id == ROW_ID)
            ).scalar_one_or_none()
            if row is None or not row.weights:
                return None
            mapped = {ScoringCategory(k): float(v) for k, v in dict(row.weights).items()}
            validate_weights(mapped)
            return row.preset, mapped, bool(row.regime_auto)
    except Exception:
        logger.debug("weight override load skipped", exc_info=True)
        return None


def save_overrides(
    preset: str,
    weights: dict[ScoringCategory, float],
    regime_auto: bool,
) -> None:
    """Upsert the singleton override row. Errors are logged, not raised."""
    payload = {cat.value: float(w) for cat, w in weights.items()}
    now = datetime.now(UTC)
    try:
        Session = _session_factory()
        if Session is None:
            return
        with Session() as session:
            stmt = pg_insert(WeightOverrideModel).values(
                id=ROW_ID,
                preset=preset,
                weights=payload,
                regime_auto=regime_auto,
                updated_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "preset": stmt.excluded.preset,
                    "weights": stmt.excluded.weights,
                    "regime_auto": stmt.excluded.regime_auto,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            session.execute(stmt)
            session.commit()
    except Exception:
        logger.warning("weight override persist failed", exc_info=True)
