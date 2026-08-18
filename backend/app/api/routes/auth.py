"""Email/password auth routes with JWT httpOnly cookies."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth_deps import get_current_user, get_optional_user
from app.core.dependencies import get_db
from app.core.rate_limit import limit_forgot_password, limit_login, limit_register
from app.core.security import (
    SESSION_COOKIE_NAME,
    cookie_secure,
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    UserSchema,
    VerifyEmailRequest,
)
from app.services.mailer import send_mail, smtp_configured

logger = logging.getLogger(__name__)

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


def _user_schema(user: User) -> UserSchema:
    return UserSchema(
        id=user.id,
        email=user.email,
        username=user.username,
        email_verified=user.email_verified,
        created_at=user.created_at,
        is_admin=settings.is_admin_username(user.username),
    )


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _issue_verify_token(user: User) -> str:
    raw = secrets.token_urlsafe(32)
    user.email_verify_token_hash = _hash_token(raw)
    user.email_verify_sent_at = datetime.now(UTC)
    return raw


def _send_verification_email(user: User, raw_token: str) -> bool:
    link = f"{settings.resolved_public_app_url()}/verify-email?token={raw_token}"
    body = (
        f"Hi {user.username},\n\n"
        f"Confirm your Signal Engine account by opening this link:\n\n"
        f"{link}\n\n"
        f"If you did not create an account, you can ignore this email.\n"
    )
    return send_mail(user.email, "Confirm your Signal Engine account", body)


def _verification_required() -> bool:
    """Require email verify when SMTP is configured, or always in production."""
    if settings.app_env.lower() == "production":
        return True
    return smtp_configured()


@router.post("/register", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> UserSchema:
    """Create an account; send verification email when required."""
    limit_register(request)
    email = body.email.lower().strip()
    username = body.username.strip()

    existing = await session.execute(
        select(User).where(
            (func.lower(User.email) == email) | (func.lower(User.username) == username.lower())
        )
    )
    conflict = existing.scalar_one_or_none()
    if conflict is not None:
        raise HTTPException(
            status_code=409,
            detail="Email or username already registered",
        )

    user = User(
        email=email,
        username=username,
        password_hash=hash_password(body.password),
    )

    if _verification_required():
        raw = _issue_verify_token(user)
        session.add(user)
        await session.flush()
        sent = _send_verification_email(user, raw)
        if not sent and settings.app_env.lower() == "production":
            logger.error("Verification email failed for %s", email)
        # No session until verified
        return _user_schema(user)

    # Local/dev without SMTP: auto-verify and log in
    user.email_verified_at = datetime.now(UTC)
    session.add(user)
    await session.flush()
    token = create_access_token(user.id)
    _set_session_cookie(response, token)
    return _user_schema(user)


@router.post("/login", response_model=UserSchema)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> UserSchema:
    """Authenticate and set the session cookie.

    When email verification is required (production, or SMTP configured),
    unverified accounts get 403 and no cookie.
    """
    email = body.email.lower().strip()
    limit_login(request, email)
    result = await session.execute(select(User).where(func.lower(User.email) == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if _verification_required() and not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required",
        )

    token = create_access_token(user.id)
    _set_session_cookie(response, token)
    return _user_schema(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    """Clear the session cookie and authenticator unlock cookie."""
    from app.core.site_gate import clear_mfa_cookie

    _clear_session_cookie(response)
    clear_mfa_cookie(response)


@router.get("/me", response_model=UserSchema)
async def me(user: User = Depends(get_current_user)) -> UserSchema:
    """Return the current authenticated user."""
    return _user_schema(user)


@router.post("/verify-email", response_model=UserSchema)
async def verify_email(
    body: VerifyEmailRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> UserSchema:
    """Mark email verified and issue a session cookie."""
    token_hash = _hash_token(body.token.strip())
    result = await session.execute(
        select(User).where(User.email_verify_token_hash == token_hash)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    user.email_verified_at = datetime.now(UTC)
    user.email_verify_token_hash = None
    await session.flush()

    token = create_access_token(user.id)
    _set_session_cookie(response, token)
    return _user_schema(user)


@router.post("/resend-verification", status_code=status.HTTP_204_NO_CONTENT)
async def resend_verification(
    body: ResendVerificationRequest,
    session: AsyncSession = Depends(get_db),
    current: User | None = Depends(get_optional_user),
) -> None:
    """Resend verification email (rate-limited). Always 204 to avoid email enumeration."""
    user: User | None = current
    if user is None and body.email:
        result = await session.execute(
            select(User).where(func.lower(User.email) == body.email.lower().strip())
        )
        user = result.scalar_one_or_none()

    if user is None or user.email_verified:
        return

    now = datetime.now(UTC)
    if user.email_verify_sent_at is not None:
        elapsed = (now - user.email_verify_sent_at).total_seconds()
        if elapsed < settings.email_verify_cooldown_seconds:
            raise HTTPException(
                status_code=429,
                detail="Please wait before requesting another verification email",
            )

    raw = _issue_verify_token(user)
    await session.flush()
    _send_verification_email(user, raw)


def _issue_reset_token(user: User) -> str:
    raw = secrets.token_urlsafe(32)
    user.password_reset_token_hash = _hash_token(raw)
    user.password_reset_sent_at = datetime.now(UTC)
    return raw


def _send_reset_email(user: User, raw_token: str) -> bool:
    link = f"{settings.resolved_public_app_url()}/reset-password?token={raw_token}"
    body = (
        f"Hi {user.username},\n\n"
        f"Reset your Signal Engine password by opening this link:\n\n"
        f"{link}\n\n"
        f"If you did not request a reset, you can ignore this email.\n"
    )
    return send_mail(user.email, "Reset your Signal Engine password", body)


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> None:
    """Email a reset link when the address exists. Always 204 to avoid enumeration."""
    limit_forgot_password(request)
    email = body.email.lower().strip()
    result = await session.execute(select(User).where(func.lower(User.email) == email))
    user = result.scalar_one_or_none()
    if user is None:
        return

    now = datetime.now(UTC)
    if user.password_reset_sent_at is not None:
        elapsed = (now - user.password_reset_sent_at).total_seconds()
        if elapsed < settings.email_verify_cooldown_seconds:
            raise HTTPException(
                status_code=429,
                detail="Please wait before requesting another reset email",
            )

    raw = _issue_reset_token(user)
    await session.flush()
    if not _send_reset_email(user, raw):
        # Still commit token so local/dev without SMTP can use DB inspection;
        # production should have SMTP. Don't leak failure to client.
        logger.warning("Password reset email not sent for %s (SMTP missing or failed)", email)


@router.post("/reset-password", response_model=UserSchema)
async def reset_password(
    body: ResetPasswordRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> UserSchema:
    """Consume reset token, set new password, and sign the user in."""
    token_hash = _hash_token(body.token.strip())
    result = await session.execute(
        select(User).where(User.password_reset_token_hash == token_hash)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    if user.password_reset_sent_at is not None:
        age_h = (datetime.now(UTC) - user.password_reset_sent_at).total_seconds() / 3600.0
        if age_h > 24:
            user.password_reset_token_hash = None
            await session.flush()
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user.password_hash = hash_password(body.password)
    user.password_reset_token_hash = None
    user.password_reset_sent_at = None
    await session.flush()

    if not (_verification_required() and not user.email_verified):
        token = create_access_token(user.id)
        _set_session_cookie(response, token)
    return _user_schema(user)
