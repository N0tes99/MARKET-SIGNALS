"""Public paper-trading agent endpoints."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from threading import Lock

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
import secrets

from app.config import settings
from app.core.auth_deps import require_admin_user
from app.core.service_dependencies import get_paper_agent
from app.engines.paper_agent.agent import PaperAgent
from app.engines.paper_agent.types import PaperTrade
from app.models.user import User
from app.schemas.paper import (
    PaperLedgerSchema,
    PaperMaturitySchema,
    PaperSummarySchema,
    PaperTradeSchema,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_TICK_LOCK = Lock()
_LAST_AUTO_TICK: datetime | None = None
_AUTO_TICK_SECONDS = 90.0
_LAST_CRON_TICK: datetime | None = None
_CRON_TICK_MIN_SECONDS = 60.0


class PaperCronTickSchema(BaseModel):
    ok: bool
    tick_notes: list[str] = Field(default_factory=list)
    last_tick_at: datetime | None = None
    open_positions: int = 0
    opens_logged: int = 0


def _require_cron_secret(x_cron_secret: str | None) -> None:
    expected = settings.cron_secret.strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="CRON_SECRET is not configured on this API",
        )
    provided = (x_cron_secret or "").strip()
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid cron secret")


def _trade_schema(t: PaperTrade) -> PaperTradeSchema:
    return PaperTradeSchema(
        id=t.id,
        symbol=t.symbol,
        source=t.source,
        setup_type=t.setup_type,
        direction=t.direction,
        fingerprint=t.fingerprint,
        signal_at=t.signal_at,
        confidence=t.confidence,
        opportunity_score=t.opportunity_score,
        size_usd=t.size_usd,
        status=t.status,
        optimistic_entry=t.optimistic_entry,
        optimistic_entry_at=t.optimistic_entry_at,
        optimistic_exit=t.optimistic_exit,
        optimistic_pnl_usd=t.optimistic_pnl_usd,
        optimistic_return_pct=t.optimistic_return_pct,
        honest_entry=t.honest_entry,
        honest_entry_at=t.honest_entry_at,
        honest_bar_ts=t.honest_bar_ts,
        honest_exit=t.honest_exit,
        honest_pnl_usd=t.honest_pnl_usd,
        honest_return_pct=t.honest_return_pct,
        mark_price=t.mark_price,
        closed_at=t.closed_at,
        close_reason=t.close_reason,
        factors=list(t.factors),
        notes=t.notes,
        signal_record_id=t.signal_record_id,
    )


def _summary_schema(agent: PaperAgent, notes: list[str] | None = None) -> PaperSummarySchema:
    s = agent.summary(tick_notes=notes)
    maturity = None
    if s.maturity is not None:
        maturity = PaperMaturitySchema(**s.maturity.__dict__)
    return PaperSummarySchema(
        agent_name=s.agent_name,
        starting_cash=s.starting_cash,
        as_of=s.as_of,
        last_tick_at=s.last_tick_at,
        optimistic=PaperLedgerSchema(**s.optimistic.__dict__),
        honest=PaperLedgerSchema(**s.honest.__dict__),
        open_trades=[_trade_schema(t) for t in s.open_trades],
        recent_closed=[_trade_schema(t) for t in s.recent_closed],
        tick_notes=list(s.tick_notes),
        maturity=maturity,
    )


def _maybe_auto_tick(agent: PaperAgent) -> list[str]:
    """Throttle living ticks so dashboard visits advance the agent without spam."""
    global _LAST_AUTO_TICK
    now = datetime.now(UTC)
    with _TICK_LOCK:
        if _LAST_AUTO_TICK is not None and now - _LAST_AUTO_TICK < timedelta(
            seconds=_AUTO_TICK_SECONDS
        ):
            return []
        _LAST_AUTO_TICK = now
    try:
        return agent.tick()
    except Exception:
        logger.exception("Paper agent auto-tick failed")
        return ["tick_error"]


@router.get("/summary", response_model=PaperSummarySchema)
async def paper_summary(
    agent: PaperAgent = Depends(get_paper_agent),
    tick: bool = True,
) -> PaperSummarySchema:
    """Public paper agent snapshot (optimistic + honest ledgers).

    Optionally advances the agent (throttled) so the bot stays \"living\".
    """
    notes: list[str] = []
    if tick:
        notes = await asyncio.to_thread(_maybe_auto_tick, agent)
    return await asyncio.to_thread(_summary_schema, agent, notes)


@router.post("/tick", response_model=PaperSummarySchema)
async def paper_tick(
    agent: PaperAgent = Depends(get_paper_agent),
) -> PaperSummarySchema:
    """Force one paper-agent tick (public; still soft-fails internally)."""
    notes = await asyncio.to_thread(agent.tick)
    return await asyncio.to_thread(_summary_schema, agent, notes)


@router.post("/cron-tick", response_model=PaperCronTickSchema)
async def paper_cron_tick(
    agent: PaperAgent = Depends(get_paper_agent),
    x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret"),
) -> PaperCronTickSchema:
    """Scheduled keep-warm tick — bypasses MFA; requires CRON_SECRET header."""
    global _LAST_CRON_TICK, _LAST_AUTO_TICK
    _require_cron_secret(x_cron_secret)
    now = datetime.now(UTC)
    with _TICK_LOCK:
        if _LAST_CRON_TICK is not None and now - _LAST_CRON_TICK < timedelta(
            seconds=_CRON_TICK_MIN_SECONDS
        ):
            summary = await asyncio.to_thread(_summary_schema, agent, ["cron:throttled"])
            return PaperCronTickSchema(
                ok=True,
                tick_notes=list(summary.tick_notes),
                last_tick_at=summary.last_tick_at,
                open_positions=summary.optimistic.open_positions,
                opens_logged=0,
            )
        _LAST_CRON_TICK = now
        _LAST_AUTO_TICK = now

    notes = await asyncio.to_thread(agent.tick)
    summary = await asyncio.to_thread(_summary_schema, agent, notes)
    opens = sum(1 for n in notes if n.startswith("open:"))
    logger.info(
        "paper_cron_tick opens=%d notes=%s last_tick=%s",
        opens,
        notes[:12],
        summary.last_tick_at,
    )
    return PaperCronTickSchema(
        ok=True,
        tick_notes=list(summary.tick_notes),
        last_tick_at=summary.last_tick_at,
        open_positions=summary.optimistic.open_positions,
        opens_logged=opens,
    )


@router.post("/reset", response_model=PaperSummarySchema)
async def paper_reset(
    agent: PaperAgent = Depends(get_paper_agent),
    _admin: User = Depends(require_admin_user),
) -> PaperSummarySchema:
    """Admin: wipe all paper trades so both ledgers restart at starting cash."""
    cleared = await asyncio.to_thread(agent.reset)
    logger.info("Paper agent reset by admin trades_cleared=%d", cleared)
    return await asyncio.to_thread(_summary_schema, agent, [f"reset_cleared:{cleared}"])
