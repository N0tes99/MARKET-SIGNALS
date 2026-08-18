"""Learnable crypto futures coefficients — paper_honest retunes radar/v2 rules.

Not the 13-category WeightOptimizer. Resolved perp_momentum paper rows
grid-search a few coefficient variants (win rate + avg return).
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass, fields, replace
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.engines.learning_engine.engine import LearningEngine
from app.engines.learning_engine.postgres_store import to_sync_database_url
from app.engines.learning_engine.types import SignalOutcome, SignalRecord
from app.models.weight_override import WeightOverrideModel

logger = logging.getLogger(__name__)

SETUP_TYPE = "perp_momentum"
MIN_CLOSED_TO_APPLY = 10
CONSERVATIVE_WIN_RATE = 40.0
# Reuse weight_overrides JSON row — id=1 is 13-category weights.
ROW_ID = 2


@dataclass(frozen=True)
class CryptoLearnCoefficients:
    """Shared radar + perp-v2 rule coefficients."""

    funding_extreme_bps: float = 8.0
    funding_soft_bps: float = 3.0
    radar_mom_12h_mult: float = 1.8
    radar_mom_20d_mult: float = 0.35
    radar_mom_align_bonus: float = 4.0
    radar_mom_fight_penalty: float = 5.0
    strong_mom_12h: float = 4.0
    strong_mom_20d: float = 15.0
    soft_mom_12h: float = 1.5
    soft_mom_20d: float = 8.0
    crowded_score_floor: float = 55.0
    running_score_floor: float = 60.0
    watch_score_floor: float = 52.0
    crowded_oi_penalty: float = 3.0
    v2_crowded_oi_penalty: float = 4.0
    v2_mom_mult: float = 2.0
    v2_min_momentum_pct: float = 1.5
    min_confidence: float = 55.0
    basis_weight: float = 2.0
    skip_crowded_opens: bool = False
    preset: str = "default"


DEFAULT_COEFFICIENTS = CryptoLearnCoefficients()

_VARIANTS: tuple[tuple[str, CryptoLearnCoefficients], ...] = (
    ("default", DEFAULT_COEFFICIENTS),
    (
        "tight_funding",
        replace(
            DEFAULT_COEFFICIENTS,
            funding_extreme_bps=10.0,
            funding_soft_bps=4.0,
            preset="learned_paper:tight_funding",
        ),
    ),
    (
        "skip_crowded",
        replace(
            DEFAULT_COEFFICIENTS,
            skip_crowded_opens=True,
            preset="learned_paper:skip_crowded",
        ),
    ),
    (
        "higher_floor",
        replace(
            DEFAULT_COEFFICIENTS,
            min_confidence=60.0,
            crowded_score_floor=58.0,
            running_score_floor=62.0,
            watch_score_floor=55.0,
            preset="learned_paper:higher_floor",
        ),
    ),
    (
        "basis_heavier",
        replace(
            DEFAULT_COEFFICIENTS,
            basis_weight=4.0,
            preset="learned_paper:basis_heavier",
        ),
    ),
)


def encode_paper_open_notes(
    *,
    setup_type: str,
    direction: str,
    factors: list[str] | None = None,
    extras: dict[str, Any] | None = None,
) -> str:
    """Structured paper-open note — parseable, still human-readable."""
    parts = [f"paper_open setup={setup_type} dir={direction}"]
    if extras:
        for key in (
            "radar_bucket",
            "radar_score",
            "funding_bps",
            "mom_12h_pct",
            "basis_pct",
        ):
            value = extras.get(key)
            if value is None or value == "":
                continue
            if isinstance(value, float):
                parts.append(f"{key}={value:.4g}")
            else:
                parts.append(f"{key}={value}")
    parts.append(f"factors={','.join((factors or [])[:4])}")
    return " ".join(parts)


def parse_paper_notes(notes: str | None) -> dict[str, Any]:
    """Pull setup / radar fields from a paper_open note string."""
    parsed: dict[str, Any] = {}
    if not notes:
        return parsed
    body = notes.split("|", 1)[0]
    for token in body.split():
        if "=" not in token:
            continue
        key, raw = token.split("=", 1)
        if key == "factors":
            parsed[key] = raw
            continue
        if key in {"radar_score", "funding_bps", "mom_12h_pct", "basis_pct"}:
            try:
                parsed[key] = float(raw)
            except ValueError:
                continue
        else:
            parsed[key] = raw
    return parsed


def setup_type_from_notes(notes: str | None) -> str | None:
    """Return setup= value from a paper note, if present."""
    parsed = parse_paper_notes(notes)
    setup = parsed.get("setup")
    return str(setup) if setup else None


def _preset_score(win_rate: float, avg_return_pct: float, total_signals: int) -> float:
    """Rank like WeightOptimizer presets: win rate + avg return."""
    if total_signals < 3:
        return -999.0
    return (win_rate * 0.4) + (avg_return_pct * 6.0) + (min(total_signals, 20) * 0.5)


def _variant_takes(record: SignalRecord, coeffs: CryptoLearnCoefficients) -> bool:
    """Would this resolved paper row still open under ``coeffs``?"""
    if record.confidence < coeffs.min_confidence:
        return False
    parsed = parse_paper_notes(record.notes)
    bucket = str(parsed.get("radar_bucket") or "")
    funding = parsed.get("funding_bps")
    extreme = False
    if isinstance(funding, (int, float)):
        extreme = abs(float(funding)) >= coeffs.funding_extreme_bps
    if coeffs.skip_crowded_opens and (bucket == "crowded" or extreme):
        return False
    return True


def _stats_for_records(records: list[SignalRecord]) -> dict[str, float | int]:
    wins = sum(1 for r in records if r.outcome == SignalOutcome.WIN.value)
    losses = sum(1 for r in records if r.outcome == SignalOutcome.LOSS.value)
    breakeven = sum(1 for r in records if r.outcome == SignalOutcome.BREAKEVEN.value)
    traded = wins + losses + breakeven
    returns = [r.realized_return_pct for r in records if r.realized_return_pct is not None]
    win_rate = round((wins / traded) * 100, 1) if traded else 0.0
    avg_ret = round(sum(returns) / len(returns), 3) if returns else 0.0
    return {
        "n": traded,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "avg_return_pct": avg_ret,
        "score": round(_preset_score(win_rate, avg_ret, traded), 2),
    }


def tune_coefficients(
    records: list[SignalRecord],
    *,
    min_closed: int = MIN_CLOSED_TO_APPLY,
) -> CryptoLearnCoefficients | None:
    """Grid-search variants against labeled perp_momentum rows. None if N < min."""
    resolved = [r for r in records if r.outcome]
    if len(resolved) < min_closed:
        return None

    ranked: list[tuple[float, CryptoLearnCoefficients]] = []
    for _name, variant in _VARIANTS:
        taken = [r for r in resolved if _variant_takes(r, variant)]
        stats = _stats_for_records(taken)
        ranked.append((float(stats["score"]), variant))

    ranked.sort(key=lambda item: item[0], reverse=True)
    winner = ranked[0][1] if ranked else DEFAULT_COEFFICIENTS

    overall = _stats_for_records(resolved)
    if float(overall["win_rate"]) < CONSERVATIVE_WIN_RATE:
        winner = replace(
            winner,
            skip_crowded_opens=True,
            min_confidence=max(winner.min_confidence, 60.0),
            preset=(
                winner.preset
                if winner.preset.startswith("learned_paper")
                else "learned_paper:conservative"
            ),
        )
        if winner.preset == "default":
            winner = replace(winner, preset="learned_paper:conservative")
    return winner


def maybe_retune_from_paper(learning: LearningEngine) -> CryptoLearnCoefficients | None:
    """Retune from paper_honest perp_momentum rows. No-op when N < 10."""
    stats = learning.outcome_stats_by_setup(SETUP_TYPE)
    rows = [
        r
        for r in learning.list_paper_memory(limit=500)
        if setup_type_from_notes(r.notes) == SETUP_TYPE and r.outcome
    ]
    winner = tune_coefficients(rows)
    if winner is None:
        return None
    get_crypto_learn_config().apply(winner, persist=True)
    logger.info(
        "crypto learn applied preset=%s n=%s win_rate=%s",
        winner.preset,
        stats.get("resolved"),
        stats.get("win_rate"),
    )
    return winner


def perp_momentum_expectancy(learning: LearningEngine) -> dict[str, float | int | None]:
    """n / win_rate for UI — zeros when the engine has no paper sample."""
    stats = learning.outcome_stats_by_setup(SETUP_TYPE)
    n = int(stats.get("resolved") or 0)
    return {
        "n": n,
        "win_rate": float(stats["win_rate"]) if n else None,
    }


def coefficients_to_payload(coeffs: CryptoLearnCoefficients) -> dict[str, Any]:
    payload = asdict(coeffs)
    payload.pop("preset", None)
    return payload


def coefficients_from_payload(
    payload: dict[str, Any],
    *,
    preset: str = "default",
) -> CryptoLearnCoefficients:
    allowed = {f.name for f in fields(CryptoLearnCoefficients)}
    kwargs: dict[str, Any] = {}
    for key, value in payload.items():
        if key not in allowed or key == "preset":
            continue
        kwargs[key] = value
    kwargs["preset"] = preset
    return replace(DEFAULT_COEFFICIENTS, **kwargs)


def _session_factory():
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    if settings.signal_store.lower().strip() == "memory":
        return None
    with _persist_lock:
        global _engine, _Session
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


_persist_lock = Lock()
_engine = None
_Session = None


def load_coefficients() -> CryptoLearnCoefficients | None:
    """Return persisted futures coefficients or None when unset / unreachable."""
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
            return coefficients_from_payload(dict(row.weights), preset=row.preset)
    except Exception:
        logger.debug("crypto learn coefficient load skipped", exc_info=True)
        return None


def save_coefficients(coeffs: CryptoLearnCoefficients) -> None:
    """Upsert the futures coefficient row. Errors are logged, not raised."""
    now = datetime.now(UTC)
    try:
        Session = _session_factory()
        if Session is None:
            return
        with Session() as session:
            stmt = pg_insert(WeightOverrideModel).values(
                id=ROW_ID,
                preset=coeffs.preset,
                weights=coefficients_to_payload(coeffs),
                regime_auto=False,
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
        logger.warning("crypto learn coefficient persist failed", exc_info=True)


class CryptoLearnConfig:
    """Thread-safe live coefficients for radar + perp v2."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._coeffs = DEFAULT_COEFFICIENTS
        self._hydrated = False

    def get(self) -> CryptoLearnCoefficients:
        with self._lock:
            return self._coeffs

    def apply(self, coeffs: CryptoLearnCoefficients, *, persist: bool = True) -> None:
        with self._lock:
            self._coeffs = coeffs
        if persist:
            save_coefficients(coeffs)

    def reset(self, *, persist: bool = True) -> None:
        self.apply(DEFAULT_COEFFICIENTS, persist=persist)

    def hydrate(self) -> bool:
        with self._lock:
            if self._hydrated:
                return False
            self._hydrated = True
        loaded = load_coefficients()
        if loaded is None:
            return False
        self.apply(loaded, persist=False)
        return True


_config = CryptoLearnConfig()


def get_crypto_learn_config() -> CryptoLearnConfig:
    """Return the process-wide futures coefficient store."""
    return _config


def get_crypto_learn_coefficients() -> CryptoLearnCoefficients:
    """Live coefficients — defaults until paper retune / hydrate."""
    return _config.get()


def hydrate_crypto_learn() -> None:
    """Startup hook — restore learned-from-paper coefficients after restart."""
    _config.hydrate()
