"""Product access gate: login → access grant → per-user TOTP → dashboard.

Authenticator secret is shown once when the user is first allowed; after they
confirm with a code, only the rotating 6-digit challenge is required.
"""

from __future__ import annotations

import logging
import secrets
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
import pyotp
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.responses import Response as StarletteResponse

from app.config import settings
from app.core.auth_deps import get_current_user, get_optional_user, require_admin_user
from app.core.dependencies import get_db
from app.core.rate_limit import limit_totp
from app.core.security import (
    JWT_ALGORITHM,
    SESSION_COOKIE_NAME,
    cookie_secure,
    decode_session_claims,
)
from app.core.totp_crypto import (
    decrypt_totp_secret,
    encrypt_totp_secret,
    is_encrypted_totp_secret,
)
from app.models.access_grant import AccessGrantModel
from app.models.user import User
from app.models.wallet import WalletAccount

logger = logging.getLogger(__name__)

MFA_COOKIE_NAME = "se_mfa"
router = APIRouter()


def gate_enabled() -> bool:
    """True when SITE_TOTP_SECRET is set (enables the gate; secrets are per-user)."""
    return bool(settings.site_totp_secret.strip())


def _clean_code(code: str) -> str:
    return "".join(ch for ch in code.strip() if ch.isdigit())


def _new_totp_secret() -> str:
    """Allocate a per-user secret that is not the shared env gate switch."""
    site = settings.site_totp_secret.strip().replace(" ", "")
    for _ in range(8):
        secret = pyotp.random_base32()
        if secret != site:
            return secret
    return pyotp.random_base32()


def _seal_user_totp_secret(user: User, plain: str) -> None:
    user.totp_secret = encrypt_totp_secret(plain)


def _upgrade_plaintext_totp_secret(user: User) -> None:
    """Rewrite legacy plaintext rows after a successful check."""
    stored = (user.totp_secret or "").strip()
    if not stored or is_encrypted_totp_secret(stored):
        return
    plain = decrypt_totp_secret(stored)
    if plain:
        _seal_user_totp_secret(user, plain)


def verify_user_totp(user: User, code: str) -> int | None:
    """Return the matching TOTP timestep, or None if invalid or replayed.

    Codes generated from SITE_TOTP_SECRET (or any other HMAC key) do not
    unlock a user — only that user's sealed authenticator secret does.
    """
    secret = decrypt_totp_secret(user.totp_secret)
    if not secret:
        return None
    cleaned = _clean_code(code)
    if len(cleaned) != 6:
        return None
    try:
        totp = pyotp.TOTP(secret)
    except Exception:
        return None
    now = int(time.time())
    interval = int(totp.interval) or 30
    for offset in (-1, 0, 1):
        for_time = now + offset * interval
        try:
            if not totp.verify(cleaned, for_time=for_time, valid_window=0):
                continue
        except Exception:
            continue
        step = for_time // interval
        last = user.totp_last_step
        if last is not None and step <= int(last):
            return None
        return int(step)
    return None


def verify_totp_code(code: str) -> bool:
    """Legacy helper for tests against the env site secret."""
    if not gate_enabled():
        return True
    secret = settings.site_totp_secret.strip().replace(" ", "")
    cleaned = _clean_code(code)
    if len(cleaned) != 6:
        return False
    try:
        return bool(pyotp.TOTP(secret).verify(cleaned, valid_window=1))
    except Exception:
        return False


def create_mfa_token(
    *,
    user_id: UUID,
    grant_expires_at: datetime | None,
    session_version: int = 0,
) -> str:
    hours = max(1, int(settings.site_gate_expire_hours))
    hard = datetime.now(UTC) + timedelta(hours=hours)
    if grant_expires_at is not None:
        grant_exp = (
            grant_expires_at
            if grant_expires_at.tzinfo
            else grant_expires_at.replace(tzinfo=UTC)
        )
        exp = min(hard, grant_exp)
    else:
        exp = hard
    payload = {
        "typ": "site_mfa",
        "sub": str(user_id),
        "sv": int(session_version),
        "jti": secrets.token_urlsafe(16),
        "exp": exp,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def decode_mfa_token(
    token: str | None,
    *,
    user_id: UUID | None = None,
    session_version: int | None = None,
) -> bool:
    """HMAC-signed MFA cookie. Forged or unsigned JWTs never unlock.

    ``user_id`` is required — a valid MFA JWT for someone else (or with no
    bound user) is not enough. ``session_version`` must match when provided
    so a stolen MFA cookie dies with logout / password reset.
    """
    if not token or user_id is None:
        return False
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        return False
    if payload.get("typ") != "site_mfa":
        return False
    sub = payload.get("sub")
    if not sub:
        return False
    if str(sub) != str(user_id):
        return False
    if session_version is not None:
        try:
            token_sv = int(payload.get("sv", 0) or 0)
        except (ValueError, TypeError):
            return False
        if token_sv != int(session_version):
            return False
    return True


def set_mfa_cookie(response: Response, token: str) -> None:
    hours = max(1, int(settings.site_gate_expire_hours))
    response.set_cookie(
        key=MFA_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=cookie_secure(),
        samesite="lax",
        max_age=hours * 3600,
        path="/",
    )


def clear_mfa_cookie(response: Response) -> None:
    response.delete_cookie(
        key=MFA_COOKIE_NAME,
        path="/",
        secure=cookie_secure(),
        httponly=True,
        samesite="lax",
    )


def is_access_public_path(path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    public = {
        "/api/v1/health",
        "/api/v1/auth/gate/status",
        "/api/v1/auth/gate/enroll",
        "/api/v1/auth/gate/verify",
        "/api/v1/auth/gate/logout",
        "/api/v1/auth/me",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/logout",
        "/api/v1/auth/verify-email",
        "/api/v1/auth/resend-verification",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/wallet/challenge",
        "/api/v1/auth/wallet/verify",
        "/api/v1/public/preview",
        # Machine keep-warm for paper ticks. Endpoint still requires X-Cron-Secret.
        "/api/v1/paper/cron-tick",
    }
    if normalized in public:
        return True
    return settings.app_env == "development" and normalized in {
        "/docs",
        "/redoc",
        "/openapi.json",
    }


def is_assets_list_path(path: str) -> bool:
    """Exact dashboard list path used by keep-warm (not /assets/{symbol})."""
    normalized = path.rstrip("/") or "/"
    return normalized == "/api/v1/assets"


def is_keep_warm_cron_path(path: str) -> bool:
    """Exact scanner paths GitHub Actions may warm with X-Cron-Secret.

    Nested routes (``/assets/{symbol}``, ``/futures/...`` besides ``/board``)
    still require a logged-in MFA session.
    """
    normalized = path.rstrip("/") or "/"
    return is_assets_list_path(path) or normalized == "/api/v1/futures/board"


def request_has_valid_cron_secret(request: Request) -> bool:
    """True when CRON_SECRET is set and matches X-Cron-Secret."""
    expected = settings.cron_secret.strip()
    if not expected:
        return False
    provided = (request.headers.get("X-Cron-Secret") or "").strip()
    if not provided:
        return False
    return secrets.compare_digest(provided, expected)


async def active_grant_for_user(
    session: AsyncSession,
    user_id: UUID,
) -> AccessGrantModel | None:
    now = datetime.now(UTC)
    stmt = (
        select(AccessGrantModel)
        .where(
            AccessGrantModel.user_id == user_id,
            AccessGrantModel.revoked_at.is_(None),
            AccessGrantModel.expires_at > now,
        )
        .order_by(AccessGrantModel.expires_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def cookie_session_has_access(
    session: AsyncSession,
    user_id: UUID,
    *,
    session_version: int | None = None,
) -> tuple[int, str] | None:
    """None if the cookie user may use data APIs; else ``(status, code)``."""
    user = await session.get(User, user_id)
    if user is None:
        return (401, "LOGIN_REQUIRED")
    if session_version is not None and int(user.session_version or 0) != int(session_version):
        return (401, "LOGIN_REQUIRED")
    if settings.is_admin_username(user.username):
        return None
    grant = await active_grant_for_user(session, user.id)
    if grant is None:
        return (403, "ACCESS_NOT_GRANTED")
    return None


class AccessGateMiddleware(BaseHTTPMiddleware):
    """When gate is on: data APIs need login + grant + MFA cookie, or a scoped API key."""

    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        if request.method == "OPTIONS":
            return await call_next(request)
        if not gate_enabled() or is_access_public_path(request.url.path):
            return await call_next(request)

        from app.core.api_keys import authenticate_api_key, extract_api_key_from_request
        from app.database.session import async_session_factory

        if extract_api_key_from_request(request) is not None:
            async with async_session_factory() as session:
                api_auth, api_error = await authenticate_api_key(request, session)
            if api_auth is not None:
                return await call_next(request)
            if api_error is not None:
                detail = {
                    "INVALID_API_KEY": "Invalid API key",
                    "API_KEY_INACTIVE": "API key revoked or expired",
                    "ACCESS_NOT_GRANTED": "API key user has no active access grant",
                    "INSUFFICIENT_SCOPE": "API key missing scope for this endpoint",
                }.get(api_error, "API key rejected")
                return JSONResponse(
                    status_code=401 if api_error != "INSUFFICIENT_SCOPE" else 403,
                    content={"detail": detail, "code": api_error},
                )

        # Keep-warm (GitHub Actions): valid cron secret may hit GET /assets
        # and GET /futures/board without MFA. Dashboard sessions still use cookies.
        if is_keep_warm_cron_path(request.url.path) and request_has_valid_cron_secret(request):
            return await call_next(request)

        session_tok = request.cookies.get(SESSION_COOKIE_NAME)
        claims = decode_session_claims(session_tok) if session_tok else None
        if claims is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Login required", "code": "LOGIN_REQUIRED"},
            )

        mfa = request.cookies.get(MFA_COOKIE_NAME)
        if not decode_mfa_token(
            mfa, user_id=claims.user_id, session_version=claims.session_version
        ):
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Authenticator unlock required",
                    "code": "MFA_REQUIRED",
                },
            )

        try:
            async with async_session_factory() as session:
                denied = await cookie_session_has_access(
                    session,
                    claims.user_id,
                    session_version=claims.session_version,
                )
        except Exception:
            logger.exception("Access grant lookup failed")
            denied = (401, "LOGIN_REQUIRED")
        if denied is not None:
            status, code = denied
            detail = {
                "LOGIN_REQUIRED": "Login required",
                "ACCESS_NOT_GRANTED": "Access not granted",
            }.get(code, "Access denied")
            return JSONResponse(
                status_code=status,
                content={"detail": detail, "code": code},
            )

        return await call_next(request)


class GateStatusSchema(BaseModel):
    enabled: bool
    expire_hours: int
    authenticated: bool = False
    is_admin: bool = False
    granted: bool = False
    grant_expires_at: datetime | None = None
    mfa_ok: bool = False
    totp_enrolled: bool = False
    next_step: str = "open"  # open | login | pending | enroll | mfa | dashboard


class GateVerifySchema(BaseModel):
    code: str = Field(default="", max_length=16)


class GateVerifyResponseSchema(BaseModel):
    ok: bool
    next_step: str
    grant_expires_at: datetime | None = None


class GateEnrollSchema(BaseModel):
    """One-time setup payload — secret is never returned after confirmation."""

    enrolled: bool
    secret: str | None = None
    otpauth_uri: str | None = None
    issuer: str
    account: str


class AccessGrantSchema(BaseModel):
    id: UUID
    user_id: UUID
    username: str
    email: str
    expires_at: datetime
    notes: str
    revoked_at: datetime | None
    created_at: datetime
    active: bool


class AccessGrantCreateSchema(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    expires_at: datetime
    notes: str = Field(default="", max_length=500)


class WaitlistUserSchema(BaseModel):
    id: UUID
    username: str
    email: str
    created_at: datetime
    email_verified: bool


class WalletAccessSchema(BaseModel):
    user_id: UUID
    username: str
    chain: str
    address: str
    created_at: datetime
    granted: bool
    grant_id: UUID | None = None
    grant_expires_at: datetime | None = None


class AccessHealthSchema(BaseModel):
    """Admin-only env dark-state — booleans, no secrets."""

    reddit: bool
    fred: bool
    gemini: bool
    discord: bool
    alert_enabled: bool
    cron_secret: bool
    strip: str


def access_health() -> AccessHealthSchema:
    """Booleans + one-line strip for the Access admin page."""
    from app.services.alert_service import AlertService

    reddit = bool(settings.reddit_client_id.strip() and settings.reddit_client_secret.strip())
    fred = bool(settings.fred_api_key.strip())
    gemini = bool(settings.gemini_api_key.strip())
    discord = AlertService.discord_configured()
    alert_on = bool(settings.alert_enabled)
    cron = bool(settings.cron_secret.strip())
    if discord and alert_on:
        discord_label = "on"
    elif discord:
        discord_label = "off"
    else:
        discord_label = "dark"
    strip = " · ".join(
        (
            f"reddit {'set' if reddit else 'dark'}",
            f"fred {'set' if fred else 'dark'}",
            f"gemini {'set' if gemini else 'dark'}",
            f"discord {discord_label}",
            f"cron {'on' if cron else 'off'}",
        )
    )
    return AccessHealthSchema(
        reddit=reddit,
        fred=fred,
        gemini=gemini,
        discord=discord,
        alert_enabled=alert_on,
        cron_secret=cron,
        strip=strip,
    )


def _user_has_access(user: User, granted: bool) -> bool:
    return granted or settings.is_admin_username(user.username)


def _next_step(
    *,
    enabled: bool,
    user: User | None,
    granted: bool,
    mfa_ok: bool,
) -> str:
    if not enabled:
        return "open"
    if user is None:
        return "login"
    if not _user_has_access(user, granted):
        return "pending"
    if not user.totp_enrolled:
        return "enroll"
    return "dashboard" if mfa_ok else "mfa"


def _ensure_pending_secret(user: User) -> str:
    """Allocate a secret for first-time setup; keep until confirmed."""
    existing = decrypt_totp_secret(user.totp_secret)
    if existing and user.totp_confirmed_at is None:
        _upgrade_plaintext_totp_secret(user)
        return existing
    if user.totp_enrolled:
        raise RuntimeError("enrolled user has no re-issuable secret")
    secret = _new_totp_secret()
    _seal_user_totp_secret(user, secret)
    user.totp_confirmed_at = None
    user.totp_last_step = None
    return secret


@router.get("/gate/status", response_model=GateStatusSchema)
async def gate_status(
    request: Request,
    user: User | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> GateStatusSchema:
    enabled = gate_enabled()
    granted = False
    grant_exp: datetime | None = None
    if user is not None:
        if settings.is_admin_username(user.username):
            granted = True
        else:
            grant = await active_grant_for_user(session, user.id)
            if grant is not None:
                granted = True
                grant_exp = grant.expires_at
    mfa_ok = bool(
        user is not None
        and decode_mfa_token(request.cookies.get(MFA_COOKIE_NAME), user_id=user.id)
    )
    if not enabled:
        mfa_ok = True
    return GateStatusSchema(
        enabled=enabled,
        expire_hours=max(1, int(settings.site_gate_expire_hours)),
        authenticated=user is not None,
        is_admin=bool(user and settings.is_admin_username(user.username)),
        granted=granted,
        grant_expires_at=grant_exp,
        mfa_ok=mfa_ok,
        totp_enrolled=bool(user and user.totp_enrolled),
        next_step=_next_step(enabled=enabled, user=user, granted=granted, mfa_ok=mfa_ok),
    )


@router.get("/gate/enroll", response_model=GateEnrollSchema)
async def gate_enroll(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> GateEnrollSchema:
    """Return setup secret once — only while the user is not yet confirmed."""
    if not gate_enabled():
        return GateEnrollSchema(
            enrolled=True,
            secret=None,
            otpauth_uri=None,
            issuer=settings.site_totp_issuer,
            account=user.username,
        )

    is_admin = settings.is_admin_username(user.username)
    grant = None if is_admin else await active_grant_for_user(session, user.id)
    if not is_admin and grant is None:
        raise HTTPException(
            status_code=403,
            detail="Access not granted yet — you are on the waitlist",
        )

    issuer = settings.site_totp_issuer.strip() or "Signal Engine"
    if user.totp_enrolled:
        return GateEnrollSchema(
            enrolled=True,
            secret=None,
            otpauth_uri=None,
            issuer=issuer,
            account=user.username,
        )

    secret = _ensure_pending_secret(user)
    await session.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.username, issuer_name=issuer)
    return GateEnrollSchema(
        enrolled=False,
        secret=secret,
        otpauth_uri=uri,
        issuer=issuer,
        account=user.username,
    )


@router.post("/gate/verify", response_model=GateVerifyResponseSchema)
async def gate_verify(
    body: GateVerifySchema,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> GateVerifyResponseSchema:
    """Confirm first-time enrollment or unlock with the user's authenticator."""
    limit_totp(request, str(user.id))
    is_admin = settings.is_admin_username(user.username)
    grant = None if is_admin else await active_grant_for_user(session, user.id)
    if not is_admin and grant is None:
        raise HTTPException(
            status_code=403,
            detail="Access not granted yet — you are on the waitlist",
        )

    if gate_enabled():
        if not user.totp_enrolled:
            _ensure_pending_secret(user)
            step = verify_user_totp(user, body.code)
            if step is None:
                await session.commit()
                raise HTTPException(status_code=401, detail="Invalid authenticator code")
            user.totp_confirmed_at = datetime.now(UTC)
            user.totp_last_step = step
            _upgrade_plaintext_totp_secret(user)
            await session.commit()
        else:
            step = verify_user_totp(user, body.code)
            if step is None:
                raise HTTPException(status_code=401, detail="Invalid authenticator code")
            user.totp_last_step = step
            _upgrade_plaintext_totp_secret(user)
            await session.commit()

    grant_exp = grant.expires_at if grant else None
    set_mfa_cookie(
        response,
        create_mfa_token(
            user_id=user.id,
            grant_expires_at=grant_exp,
            session_version=int(user.session_version or 0),
        ),
    )
    return GateVerifyResponseSchema(
        ok=True,
        next_step="dashboard",
        grant_expires_at=grant_exp,
    )


@router.post("/gate/logout", response_model=GateStatusSchema)
async def gate_logout(
    request: Request,
    response: Response,
    user: User | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> GateStatusSchema:
    clear_mfa_cookie(response)
    return await gate_status(request, user, session)


@router.get("/access/health", response_model=AccessHealthSchema)
async def access_env_health(
    _admin: User = Depends(require_admin_user),
) -> AccessHealthSchema:
    """Which optional keys are present — no secret values."""
    return access_health()


@router.get("/access/waitlist", response_model=list[WaitlistUserSchema])
async def list_waitlist(
    _admin: User = Depends(require_admin_user),
    session: AsyncSession = Depends(get_db),
) -> list[WaitlistUserSchema]:
    """Users with no active grant — the operator waitlist inbox."""
    now = datetime.now(UTC)
    active_ids = select(AccessGrantModel.user_id).where(
        AccessGrantModel.revoked_at.is_(None),
        AccessGrantModel.expires_at > now,
    )
    wallet_ids = select(WalletAccount.user_id)
    rows = (
        await session.execute(
            select(User)
            .where(User.id.notin_(active_ids), User.id.notin_(wallet_ids))
            .order_by(User.created_at.desc())
            .limit(80)
        )
    ).scalars().all()
    return [
        WaitlistUserSchema(
            id=u.id,
            username=u.username,
            email=u.email,
            created_at=u.created_at,
            email_verified=u.email_verified,
        )
        for u in rows
        if not settings.is_admin_username(u.username)
    ]


@router.get("/access/wallets", response_model=list[WalletAccessSchema])
async def list_wallet_users(
    _admin: User = Depends(require_admin_user),
    session: AsyncSession = Depends(get_db),
) -> list[WalletAccessSchema]:
    """Wallet-linked accounts — addresses stay on this admin inbox only."""
    now = datetime.now(UTC)
    rows = (
        await session.execute(
            select(WalletAccount, User)
            .join(User, User.id == WalletAccount.user_id)
            .order_by(WalletAccount.created_at.desc())
            .limit(200)
        )
    ).all()
    user_ids = [u.id for _link, u in rows]
    grants_by_user: dict[UUID, AccessGrantModel] = {}
    if user_ids:
        grant_rows = (
            await session.execute(
                select(AccessGrantModel)
                .where(
                    AccessGrantModel.user_id.in_(user_ids),
                    AccessGrantModel.revoked_at.is_(None),
                    AccessGrantModel.expires_at > now,
                )
                .order_by(AccessGrantModel.expires_at.desc())
            )
        ).scalars().all()
        for grant in grant_rows:
            grants_by_user.setdefault(grant.user_id, grant)

    out: list[WalletAccessSchema] = []
    for link, u in rows:
        grant = grants_by_user.get(u.id)
        out.append(
            WalletAccessSchema(
                user_id=u.id,
                username=u.username,
                chain=link.chain,
                address=link.address,
                created_at=link.created_at,
                granted=grant is not None,
                grant_id=grant.id if grant else None,
                grant_expires_at=grant.expires_at if grant else None,
            )
        )
    return out


@router.get("/access/grants", response_model=list[AccessGrantSchema])
async def list_grants(
    _admin: User = Depends(require_admin_user),
    session: AsyncSession = Depends(get_db),
) -> list[AccessGrantSchema]:
    now = datetime.now(UTC)
    rows = (
        await session.execute(
            select(AccessGrantModel, User)
            .join(User, User.id == AccessGrantModel.user_id)
            .order_by(AccessGrantModel.created_at.desc())
            .limit(200)
        )
    ).all()
    out: list[AccessGrantSchema] = []
    for grant, u in rows:
        active = grant.revoked_at is None and grant.expires_at > now
        email = u.email
        if email.endswith("@wallets.signalengine.app"):
            email = "wallet account"
        out.append(
            AccessGrantSchema(
                id=grant.id,
                user_id=u.id,
                username=u.username,
                email=email,
                expires_at=grant.expires_at,
                notes=grant.notes or "",
                revoked_at=grant.revoked_at,
                created_at=grant.created_at,
                active=active,
            )
        )
    return out


@router.post("/access/grants", response_model=AccessGrantSchema)
async def create_grant(
    body: AccessGrantCreateSchema,
    admin: User = Depends(require_admin_user),
    session: AsyncSession = Depends(get_db),
) -> AccessGrantSchema:
    from sqlalchemy import func as sqla_func

    username = body.username.strip()
    result = await session.execute(
        select(User).where(sqla_func.lower(User.username) == username.lower())
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")

    exp = body.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=UTC)
    if exp <= datetime.now(UTC):
        raise HTTPException(status_code=400, detail="expires_at must be in the future")

    grant = AccessGrantModel(
        user_id=target.id,
        granted_by_user_id=admin.id,
        expires_at=exp,
        notes=body.notes.strip(),
    )
    session.add(grant)
    await session.commit()
    await session.refresh(grant)
    return AccessGrantSchema(
        id=grant.id,
        user_id=target.id,
        username=target.username,
        email=target.email,
        expires_at=grant.expires_at,
        notes=grant.notes or "",
        revoked_at=grant.revoked_at,
        created_at=grant.created_at,
        active=True,
    )


@router.post("/access/grants/{grant_id}/revoke", response_model=AccessGrantSchema)
async def revoke_grant(
    grant_id: UUID,
    _admin: User = Depends(require_admin_user),
    session: AsyncSession = Depends(get_db),
) -> AccessGrantSchema:
    grant = await session.get(AccessGrantModel, grant_id)
    if grant is None:
        raise HTTPException(status_code=404, detail="Grant not found")
    grant.revoked_at = datetime.now(UTC)
    await session.commit()
    user = await session.get(User, grant.user_id)
    return AccessGrantSchema(
        id=grant.id,
        user_id=grant.user_id,
        username=user.username if user else "",
        email=user.email if user else "",
        expires_at=grant.expires_at,
        notes=grant.notes or "",
        revoked_at=grant.revoked_at,
        created_at=grant.created_at,
        active=False,
    )
