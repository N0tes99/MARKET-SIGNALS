"""Admin + user API key management."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.api_keys import (
    AVAILABLE_SCOPES,
    generate_api_key,
    normalize_scopes,
    resolve_api_key_expiry,
)
from app.core.auth_deps import get_current_user, require_admin_user
from app.core.dependencies import get_db
from app.models.api_key import ApiKeyModel
from app.models.user import User

router = APIRouter()


class ApiKeySchema(BaseModel):
    id: UUID
    user_id: UUID
    username: str
    name: str
    key_prefix: str
    scopes: list[str]
    expires_at: datetime | None
    revoked_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    active: bool


class ApiKeyCreateSchema(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    name: str = Field(default="", max_length=120)
    scopes: list[str] = Field(..., min_length=1)
    expires_at: datetime | None = None


class ApiKeyCreatedSchema(ApiKeySchema):
    secret: str = Field(..., description="Full key — shown once at creation")


class ApiKeyScopesSchema(BaseModel):
    scopes: list[str]


def _is_active(key: ApiKeyModel) -> bool:
    if key.revoked_at is not None:
        return False
    if key.expires_at is None:
        return True
    exp = key.expires_at if key.expires_at.tzinfo else key.expires_at.replace(tzinfo=UTC)
    return exp > datetime.now(UTC)


def _to_schema(key: ApiKeyModel, user: User) -> ApiKeySchema:
    return ApiKeySchema(
        id=key.id,
        user_id=key.user_id,
        username=user.username,
        name=key.name or "",
        key_prefix=key.key_prefix,
        scopes=list(key.scopes or []),
        expires_at=key.expires_at,
        revoked_at=key.revoked_at,
        last_used_at=key.last_used_at,
        created_at=key.created_at,
        active=_is_active(key),
    )


@router.get("/access/api-keys/scopes", response_model=ApiKeyScopesSchema)
async def list_available_scopes(
    _admin: User = Depends(require_admin_user),
) -> ApiKeyScopesSchema:
    return ApiKeyScopesSchema(scopes=list(AVAILABLE_SCOPES))


@router.get("/access/api-keys", response_model=list[ApiKeySchema])
async def admin_list_api_keys(
    _admin: User = Depends(require_admin_user),
    session: AsyncSession = Depends(get_db),
) -> list[ApiKeySchema]:
    rows = (
        await session.execute(
            select(ApiKeyModel, User)
            .join(User, User.id == ApiKeyModel.user_id)
            .order_by(ApiKeyModel.created_at.desc())
            .limit(200)
        )
    ).all()
    return [_to_schema(key, user) for key, user in rows]


@router.post("/access/api-keys", response_model=ApiKeyCreatedSchema)
async def admin_create_api_key(
    body: ApiKeyCreateSchema,
    admin: User = Depends(require_admin_user),
    session: AsyncSession = Depends(get_db),
) -> ApiKeyCreatedSchema:
    username = body.username.strip()
    result = await session.execute(
        select(User).where(func.lower(User.username) == username.lower())
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")
    if settings.is_admin_username(target.username):
        raise HTTPException(
            status_code=400,
            detail="API keys cannot be issued for admin accounts",
        )

    if body.expires_at is not None:
        try:
            expires_at = resolve_api_key_expiry(body.expires_at)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        expires_at = resolve_api_key_expiry(None)

    try:
        scopes = normalize_scopes(body.scopes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    full_key, key_prefix, key_hash = generate_api_key()
    record = ApiKeyModel(
        user_id=target.id,
        created_by_user_id=admin.id,
        name=body.name.strip(),
        key_prefix=key_prefix,
        key_hash=key_hash,
        scopes=scopes,
        expires_at=expires_at,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    base = _to_schema(record, target)
    return ApiKeyCreatedSchema(**base.model_dump(), secret=full_key)


@router.post("/access/api-keys/{key_id}/revoke", response_model=ApiKeySchema)
async def admin_revoke_api_key(
    key_id: UUID,
    _admin: User = Depends(require_admin_user),
    session: AsyncSession = Depends(get_db),
) -> ApiKeySchema:
    row = (
        await session.execute(
            select(ApiKeyModel, User)
            .join(User, User.id == ApiKeyModel.user_id)
            .where(ApiKeyModel.id == key_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="API key not found")
    key, user = row
    if key.revoked_at is None:
        key.revoked_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(key)
    return _to_schema(key, user)


@router.get("/me/api-keys", response_model=list[ApiKeySchema])
async def list_my_api_keys(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[ApiKeySchema]:
    rows = (
        await session.execute(
            select(ApiKeyModel)
            .where(ApiKeyModel.user_id == user.id)
            .order_by(ApiKeyModel.created_at.desc())
        )
    ).scalars().all()
    return [_to_schema(key, user) for key in rows]


@router.post("/me/api-keys/{key_id}/revoke", response_model=ApiKeySchema)
async def revoke_my_api_key(
    key_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiKeySchema:
    key = await session.get(ApiKeyModel, key_id)
    if key is None or key.user_id != user.id:
        raise HTTPException(status_code=404, detail="API key not found")
    if key.revoked_at is None:
        key.revoked_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(key)
    return _to_schema(key, user)
