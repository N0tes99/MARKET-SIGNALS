"""User favorites (tracked symbols watchlist)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_deps import get_current_user, require_verified_user
from app.core.dependencies import get_db
from app.market_data.symbols import is_tracked
from app.models.favorite import Favorite
from app.models.user import User
from app.schemas.social import AddFavoriteRequest, FavoriteSchema

router = APIRouter()


@router.get("", response_model=list[FavoriteSchema])
async def list_favorites(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[FavoriteSchema]:
    """List the current user's favorite symbols."""
    result = await session.execute(
        select(Favorite)
        .where(Favorite.user_id == user.id)
        .order_by(Favorite.created_at.desc())
    )
    rows = result.scalars().all()
    return [FavoriteSchema(symbol=r.symbol, created_at=r.created_at) for r in rows]


@router.put("", response_model=FavoriteSchema, status_code=status.HTTP_201_CREATED)
async def add_favorite(
    body: AddFavoriteRequest,
    user: User = Depends(require_verified_user),
    session: AsyncSession = Depends(get_db),
) -> FavoriteSchema:
    """Add a tracked symbol to favorites (idempotent create)."""
    normalized = body.symbol.upper().strip()
    if not is_tracked(normalized):
        raise HTTPException(
            status_code=400,
            detail=f"Symbol '{normalized}' is not tracked",
        )

    existing = await session.execute(
        select(Favorite).where(
            Favorite.user_id == user.id,
            Favorite.symbol == normalized,
        )
    )
    fav = existing.scalar_one_or_none()
    if fav is not None:
        return FavoriteSchema(symbol=fav.symbol, created_at=fav.created_at)

    fav = Favorite(user_id=user.id, symbol=normalized)
    session.add(fav)
    await session.flush()
    return FavoriteSchema(symbol=fav.symbol, created_at=fav.created_at)


@router.delete("/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    symbol: str,
    user: User = Depends(require_verified_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Remove a symbol from favorites."""
    normalized = symbol.upper().strip()
    result = await session.execute(
        select(Favorite).where(
            Favorite.user_id == user.id,
            Favorite.symbol == normalized,
        )
    )
    fav = result.scalar_one_or_none()
    if fav is not None:
        await session.delete(fav)
        await session.flush()
