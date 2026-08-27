"""Fail-open ops snapshots for the OHLCV warehouse and Alembic revision."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.config import settings
from app.data_lake.warehouse.ohlcv import _skip_postgres, warehouse_status
from app.engines.learning_engine.postgres_store import to_sync_database_url

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def alembic_head() -> str | None:
    """Head revision from the Alembic script directory (no DB)."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        cfg = Config(str(_BACKEND_ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(_BACKEND_ROOT / "alembic"))
        cfg.set_main_option("path_separator", "os")
        return ScriptDirectory.from_config(cfg).get_current_head()
    except Exception:
        logger.debug("alembic head lookup skipped", exc_info=True)
        return None


def alembic_status() -> dict[str, object]:
    """Current vs head revision. Never raises."""
    head = alembic_head()
    if _skip_postgres():
        return {
            "current": None,
            "head": head,
            "at_head": False,
            "source": "skipped",
        }
    try:
        url = to_sync_database_url(settings.database_url)
        engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_timeout=3,
            connect_args={"connect_timeout": 2},
        )
        with engine.connect() as conn:
            if not inspect(engine).has_table("alembic_version"):
                return {
                    "current": None,
                    "head": head,
                    "at_head": False,
                    "source": "missing",
                }
            current = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        current_s = str(current) if current is not None else None
        return {
            "current": current_s,
            "head": head,
            "at_head": bool(current_s and head and current_s == head),
            "source": "postgres",
        }
    except Exception:
        logger.debug("alembic status skipped", exc_info=True)
        return {
            "current": None,
            "head": head,
            "at_head": False,
            "source": "error",
        }


def lake_ops_snapshot() -> dict[str, object]:
    """Warehouse + Alembic, for health and /data-lake/status."""
    warehouse = warehouse_status()
    alembic = alembic_status()
    latest = warehouse.get("latest_ts")
    return {
        "warehouse": {
            "backend": warehouse["backend"],
            "table_present": warehouse["table_present"],
            "bar_count": warehouse["bar_count"],
            "symbol_count": warehouse["symbol_count"],
            "latest_ts": latest.isoformat() if hasattr(latest, "isoformat") else latest,
        },
        "alembic": alembic,
    }
