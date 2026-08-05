"""Email/password auth routes with JWT httpOnly cookies."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth_deps import get_current_user
from app.core.dependencies import get_db
from app.core.security import (
    SESSION_COOKIE_NAME,
    cookie_secure,
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, UserSchema

router = APIRouter()


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=cookie_secure(),
        samesite="lax",
        path="/",
        max_age=settings.access_token_expire_minutes * 60,
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=cookie_secure(),
        httponly=True,
        samesite="lax",
    )


@router.post("/register", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> User:
    """Create an account and set the session cookie."""
    email = body.email.lower().strip()
    username = body.username.strip()

    existing = await session.execute(
        select(User).where(
            (func.lower(User.email) == email) | (func.lower(User.username) == username.lower())
        )
    )
    conflict = existing.scalar_one_or_none()
    if conflict is not None:
        if conflict.email.lower() == email:
            raise HTTPException(status_code=409, detail="Email already registered")
        raise HTTPException(status_code=409, detail="Username already taken")

    user = User(
        email=email,
        username=username,
        password_hash=hash_password(body.password),
    )
    session.add(user)
    await session.flush()

    token = create_access_token(user.id)
    _set_session_cookie(response, token)
    return user


@router.post("/login", response_model=UserSchema)
async def login(
    body: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> User:
    """Authenticate and set the session cookie."""
    email = body.email.lower().strip()
    result = await session.execute(select(User).where(func.lower(User.email) == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.id)
    _set_session_cookie(response, token)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    """Clear the session cookie."""
    _clear_session_cookie(response)


@router.get("/me", response_model=UserSchema)
async def me(user: User = Depends(get_current_user)) -> User:
    """Return the current authenticated user."""
    return user
