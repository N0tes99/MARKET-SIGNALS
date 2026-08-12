"""Ticker add-requests from users → admin inbox."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth_deps import get_current_user, require_admin_user
from app.core.dependencies import get_db
from app.models.ticker_request import TickerRequestModel
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

_SYMBOL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9.\-]{0,15}$")
_MAX_OPEN_PER_USER = 5
_MAX_PER_DAY = 8


class TickerRequestCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    message: str = Field(default="", max_length=1000)


class TickerRequestSchema(BaseModel):
    id: UUID
    user_id: UUID
    username: str
    symbol: str
    message: str
    status: str
    admin_note: str
    created_at: datetime
    resolved_at: datetime | None


class TickerRequestResolve(BaseModel):
    status: str = Field(pattern="^(done|dismissed|open)$")
    admin_note: str = Field(default="", max_length=500)


def _normalize_symbol(raw: str) -> str:
    sym = raw.strip().upper().lstrip("$")
    if not _SYMBOL_RE.match(sym):
        raise HTTPException(
            status_code=400,
            detail="Symbol must be letters/numbers (e.g. NVDA, BTC)",
        )
    return sym


def _to_schema(row: TickerRequestModel) -> TickerRequestSchema:
    username = row.user.username if row.user is not None else ""
    return TickerRequestSchema(
        id=row.id,
        user_id=row.user_id,
        username=username,
        symbol=row.symbol,
        message=row.message or "",
        status=row.status,
        admin_note=row.admin_note or "",
        created_at=row.created_at,
        resolved_at=row.resolved_at,
    )


def _notify_admin_discord(*, username: str, symbol: str, message: str) -> None:
    """Best-effort ping via existing alert Discord webhook."""
    webhook = settings.alert_discord_webhook_url.strip()
    if not webhook:
        return
    body = {
        "username": "Signal Engine",
        "embeds": [
            {
                "title": f"Ticker request: {symbol}",
                "description": (message[:500] or "_No message_"),
                "color": 0x8FA88A,
                "fields": [
                    {"name": "From", "value": f"@{username}", "inline": True},
                    {"name": "Symbol", "value": symbol, "inline": True},
                ],
            }
        ],
    }
    try:
        with httpx.Client(timeout=6.0) as client:
            client.post(webhook, json=body).raise_for_status()
    except Exception:
        logger.warning("Discord ticker-request notify failed", exc_info=True)


@router.post("", response_model=TickerRequestSchema)
async def create_ticker_request(
    body: TickerRequestCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TickerRequestSchema:
    """Logged-in user asks admin to track a ticker."""
    symbol = _normalize_symbol(body.symbol)
    message = body.message.strip()

    open_count = (
        await session.execute(
            select(func.count())
            .select_from(TickerRequestModel)
            .where(
                TickerRequestModel.user_id == user.id,
                TickerRequestModel.status == "open",
            )
        )
    ).scalar_one()
    if int(open_count) >= _MAX_OPEN_PER_USER:
        raise HTTPException(
            status_code=429,
            detail=f"You already have {_MAX_OPEN_PER_USER} open requests — wait for admin review",
        )

    day_ago = datetime.now(UTC) - timedelta(days=1)
    day_count = (
        await session.execute(
            select(func.count())
            .select_from(TickerRequestModel)
            .where(
                TickerRequestModel.user_id == user.id,
                TickerRequestModel.created_at >= day_ago,
            )
        )
    ).scalar_one()
    if int(day_count) >= _MAX_PER_DAY:
        raise HTTPException(status_code=429, detail="Daily request limit reached — try again tomorrow")

    row = TickerRequestModel(
        user_id=user.id,
        symbol=symbol,
        message=message,
        status="open",
        admin_note="",
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    # ensure relationship loaded
    _ = row.user
    _notify_admin_discord(username=user.username, symbol=symbol, message=message)
    return _to_schema(row)


@router.get("/mine", response_model=list[TickerRequestSchema])
async def list_my_ticker_requests(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[TickerRequestSchema]:
    rows = (
        await session.execute(
            select(TickerRequestModel)
            .where(TickerRequestModel.user_id == user.id)
            .order_by(TickerRequestModel.created_at.desc())
            .limit(30)
        )
    ).scalars().all()
    return [_to_schema(r) for r in rows]


@router.get("/admin", response_model=list[TickerRequestSchema])
async def list_ticker_requests_admin(
    _admin: User = Depends(require_admin_user),
    session: AsyncSession = Depends(get_db),
    status: str | None = None,
) -> list[TickerRequestSchema]:
    stmt = select(TickerRequestModel).order_by(TickerRequestModel.created_at.desc()).limit(100)
    if status:
        stmt = stmt.where(TickerRequestModel.status == status)
    rows = (await session.execute(stmt)).scalars().all()
    return [_to_schema(r) for r in rows]


@router.post("/admin/{request_id}/resolve", response_model=TickerRequestSchema)
async def resolve_ticker_request(
    request_id: UUID,
    body: TickerRequestResolve,
    _admin: User = Depends(require_admin_user),
    session: AsyncSession = Depends(get_db),
) -> TickerRequestSchema:
    row = await session.get(TickerRequestModel, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found")
    row.status = body.status
    row.admin_note = body.admin_note.strip()
    row.resolved_at = None if body.status == "open" else datetime.now(UTC)
    await session.commit()
    await session.refresh(row)
    return _to_schema(row)
