"""Expansion policy versions — Postgres when migrated, else file defaults."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from threading import Lock

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.engines.expansion_engine.config import (
    DEFAULT_EXPANSION_CONFIG,
    ExpansionConfig,
    expansion_config_from_dict,
    expansion_config_to_dict,
    file_expansion_config,
)
from app.engines.learning_engine.postgres_store import to_sync_database_url
from app.models.procedural_policy import ProceduralPolicyModel

logger = logging.getLogger(__name__)

EXPANSION_POLICY = "expansion"

_lock = Lock()
_engine = None
_Session = None
_memory_knobs: dict[str, object] | None = None
_memory_version = 0


def _skip_postgres() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    return settings.signal_store.lower().strip() == "memory"


def _session_factory():
    global _engine, _Session
    if _skip_postgres():
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
        if not inspect(_engine).has_table("procedural_policies"):
            logger.warning("procedural_policies missing — using file expansion knobs")
            return None
        _Session = sessionmaker(bind=_engine, expire_on_commit=False)
        return _Session


def load_expansion_config() -> ExpansionConfig:
    """Active expansion knobs (Postgres overlay, else compiled defaults)."""
    if _memory_knobs is not None:
        return expansion_config_from_dict(_memory_knobs)
    try:
        Session = _session_factory()
        if Session is None:
            return file_expansion_config()
        with Session() as session:
            row = session.execute(
                select(ProceduralPolicyModel).where(
                    ProceduralPolicyModel.name == EXPANSION_POLICY
                )
            ).scalar_one_or_none()
            if row is None or not row.knobs:
                return file_expansion_config()
            return expansion_config_from_dict(dict(row.knobs))
    except Exception:
        logger.debug("procedural policy load skipped", exc_info=True)
        return file_expansion_config()


def policy_meta() -> dict[str, object]:
    """Source + version for the expansion policy (file vs postgres vs memory)."""
    if _memory_knobs is not None:
        return {
            "name": EXPANSION_POLICY,
            "source": "memory",
            "version": _memory_version,
            "knobs": expansion_config_to_dict(load_expansion_config()),
        }
    try:
        Session = _session_factory()
        if Session is None:
            return {
                "name": EXPANSION_POLICY,
                "source": "file",
                "version": 0,
                "knobs": expansion_config_to_dict(file_expansion_config()),
            }
        with Session() as session:
            row = session.execute(
                select(ProceduralPolicyModel).where(
                    ProceduralPolicyModel.name == EXPANSION_POLICY
                )
            ).scalar_one_or_none()
            if row is None:
                return {
                    "name": EXPANSION_POLICY,
                    "source": "file",
                    "version": 0,
                    "knobs": expansion_config_to_dict(file_expansion_config()),
                }
            return {
                "name": EXPANSION_POLICY,
                "source": "postgres",
                "version": int(row.version),
                "knobs": expansion_config_to_dict(
                    expansion_config_from_dict(dict(row.knobs))
                ),
            }
    except Exception:
        logger.debug("procedural policy meta skipped", exc_info=True)
        return {
            "name": EXPANSION_POLICY,
            "source": "file",
            "version": 0,
            "knobs": expansion_config_to_dict(file_expansion_config()),
        }


def save_expansion_config(cfg: ExpansionConfig) -> dict[str, object]:
    """Upsert expansion knobs. Fail-open to in-process overlay."""
    global _memory_knobs, _memory_version
    payload = expansion_config_to_dict(cfg)
    now = datetime.now(UTC)
    try:
        Session = _session_factory()
        if Session is None:
            _memory_knobs = payload
            _memory_version += 1
            return policy_meta()
        with Session() as session:
            current = session.execute(
                select(ProceduralPolicyModel).where(
                    ProceduralPolicyModel.name == EXPANSION_POLICY
                )
            ).scalar_one_or_none()
            next_version = int(current.version) + 1 if current is not None else 1
            stmt = pg_insert(ProceduralPolicyModel).values(
                name=EXPANSION_POLICY,
                version=next_version,
                knobs=payload,
                updated_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["name"],
                set_={
                    "version": stmt.excluded.version,
                    "knobs": stmt.excluded.knobs,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            session.execute(stmt)
            session.commit()
        _memory_knobs = None
        return policy_meta()
    except Exception:
        logger.warning("procedural policy persist failed — using process overlay", exc_info=True)
        _memory_knobs = payload
        _memory_version += 1
        return policy_meta()


def reset_expansion_config() -> dict[str, object]:
    """Restore compiled-in defaults."""
    return save_expansion_config(DEFAULT_EXPANSION_CONFIG)


def reset_process_overlay() -> None:
    """Drop the in-process overlay (tests)."""
    global _memory_knobs, _memory_version
    _memory_knobs = None
    _memory_version = 0


def active_expansion_policy() -> dict[str, object]:
    """Public snapshot used by cortex/docs."""
    meta = policy_meta()
    knobs = dict(meta["knobs"])  # type: ignore[arg-type]
    return {
        "source": meta["source"],
        "version": meta["version"],
        "universe": knobs.get("universe"),
        "primed_min_compression": knobs.get("primed_min_compression"),
        "trigger_volume_mult": knobs.get("trigger_volume_mult"),
        "watch_net_score": knobs.get("watch_net_score"),
        "primed_net_score": knobs.get("primed_net_score"),
        "trigger_net_score": knobs.get("trigger_net_score"),
    }
