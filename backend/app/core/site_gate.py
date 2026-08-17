"""Product access gate: login → access grant → per-user TOTP → dashboard.

Authenticator secret is shown once when the user is first allowed; after they
confirm with a code, only the rotating 6-digit challenge is required.
"""

from __future__ import annotations

import secrets
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
from app.core.security import JWT_ALGORITHM, SESSION_COOKIE_NAME, cookie_secure, decode_access_token
from app.models.access_grant import AccessGrantModel
from app.models.user import User
from app.models.wallet import WalletAccount

MFA_COOKIE_NAME = "se_mfa"
router = APIRouter()


def gate_enabled() -> bool:
    """True when SITE_TOTP_SECRET is set (enables the gate; secrets are per-user)."""
    return bool(settings.site_totp_secret.strip())


def _clean_code(code: str) -> str:
    return "".join(ch for ch in code.strip() if ch.isdigit())


def verify_user_totp(user: User, code: str) -> bool:
    secret = (user.totp_secret or "").strip().replace(" ", "")
    if not secret:
        return False
    cleaned = _clean_code(code)
    if len(cleaned) != 6:
        return False
    try:
        return bool(pyotp.TOTP(secret).verify(cleaned, valid_window=1))
    except Exception:
        return False


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


def create_mfa_token(*, user_id: UUID, grant_expires_at: datetime | None) -> str:
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
        "exp": exp,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def decode_mfa_token(token: str | None, *, user_id: UUID | None = None) -> bool:
    if not token:
        return False
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return False
    if payload.get("typ") != "site_mfa":
        return False
    return not (user_id is not None and str(payload.get("sub")) != str(user_id))


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
    response.delete_cookie(key=MFA_COOKIE_NAME, path="/")


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
    # Admin waitlist / grants — require_admin_user so /admin/access works after MFA.
    if normalized.startswith("/api/v1/auth/access/"):
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


class AccessGateMiddleware(BaseHTTPMiddleware):
    """When gate is on: data APIs need login + grant + MFA cookie."""

    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        if request.method == "OPTIONS":
            return await call_next(request)
        if not gate_enabled() or is_access_public_path(request.url.path):
            return await call_next(request)
        # Keep-warm (GitHub Actions): valid cron secret may hit GET /assets
        # without MFA. Logged-in dashboard sessions still use cookies below.
        if is_assets_list_path(request.url.path) and request_has_valid_cron_secret(request):
            return await call_next(request)

        session_tok = request.cookies.get(SESSION_COOKIE_NAME)
        user_id = decode_access_token(session_tok) if session_tok else None
        if user_id is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Login required", "code": "LOGIN_REQUIRED"},
            )

        mfa = request.cookies.get(MFA_COOKIE_NAME)
        if not decode_mfa_token(mfa, user_id=user_id):
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Authenticator unlock required",
                    "code": "MFA_REQUIRED",
                },
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
    existing = (user.totp_secret or "").strip().replace(" ", "")
    if existing and user.totp_confirmed_at is None:
        return existing
    if user.totp_enrolled:
        raise RuntimeError("enrolled user has no re-issuable secret")
    secret = pyotp.random_base32()
    user.totp_secret = secret
    user.totp_confirmed_at = None
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
    response: Response,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> GateVerifyResponseSchema:
    """Confirm first-time enrollment or unlock with the user's authenticator."""
    limit_totp(str(user.id))
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
            if not verify_user_totp(user, body.code):
                await session.commit()
                raise HTTPException(status_code=401, detail="Invalid authenticator code")
            user.totp_confirmed_at = datetime.now(UTC)
            await session.commit()
        elif not verify_user_totp(user, body.code):
            raise HTTPException(status_code=401, detail="Invalid authenticator code")

    grant_exp = grant.expires_at if grant else None
    set_mfa_cookie(response, create_mfa_token(user_id=user.id, grant_expires_at=grant_exp))
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
