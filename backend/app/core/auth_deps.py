"""FastAPI dependencies for social (JWT cookie) auth."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dependencies import get_db
from app.core.security import SESSION_COOKIE_NAME, decode_access_token
from app.models.user import User


async def _user_from_cookie(
    request: Request,
    session: AsyncSession,
) -> User | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    user_id = decode_access_token(token)
    if user_id is None:
        return None
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> User:
    """Require a valid session cookie; raise 401 otherwise."""
    user = await _user_from_cookie(request, session)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


async def get_optional_user(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> User | None:
    """Return the current user if logged in, else None."""
    return await _user_from_cookie(request, session)


async def require_verified_user(
    user: User = Depends(get_current_user),
) -> User:
    """Require login and a verified email for write actions."""
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required",
        )
    return user


async def require_admin_user(
    user: User = Depends(get_current_user),
) -> User:
    """Require login as an ADMIN_USERNAMES account (Outcome log, etc.)."""
    if not settings.is_admin_username(user.username):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
