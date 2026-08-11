"""Ethereum wallet message-sign login (SIWE-style)."""

from __future__ import annotations

import logging
import re
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import is_address, to_checksum_address
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dependencies import get_db
from app.core.security import SESSION_COOKIE_NAME, cookie_secure, create_access_token, hash_password
from app.models.user import User
from app.models.wallet import WalletAccount, WalletAuthChallenge
from app.schemas.auth import UserSchema

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wallet")

CHAIN_ETHEREUM = "ethereum"
CHALLENGE_TTL_MINUTES = 10
_ETH_ADDR_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


class WalletChallengeRequest(BaseModel):
    chain: str = Field(default=CHAIN_ETHEREUM, max_length=32)
    address: str = Field(min_length=42, max_length=128)
    chain_id: int = Field(default=1, ge=1)


class WalletChallengeResponse(BaseModel):
    chain: str
    address: str
    nonce: str
    message: str
    expires_at: datetime


class WalletVerifyRequest(BaseModel):
    chain: str = Field(default=CHAIN_ETHEREUM, max_length=32)
    address: str = Field(min_length=42, max_length=128)
    signature: str = Field(min_length=8, max_length=256)
    nonce: str = Field(min_length=8, max_length=64)


def _normalize_eth_address(address: str) -> str:
    raw = address.strip()
    if not _ETH_ADDR_RE.match(raw) or not is_address(raw):
        raise HTTPException(status_code=400, detail="Invalid Ethereum address")
    return to_checksum_address(raw)


def _app_domain() -> str:
    base = settings.resolved_public_app_url().rstrip("/")
    host = urlparse(base).hostname
    return host or "localhost"


def _build_siwe_message(*, address: str, nonce: str, chain_id: int, expires_at: datetime) -> str:
    domain = _app_domain()
    uri = settings.resolved_public_app_url().rstrip("/")
    issued = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    expiration = expires_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        f"{domain} wants you to sign in with your Ethereum account:\n"
        f"{address}\n"
        f"\n"
        f"Sign in to Signal Engine. This request will not trigger a blockchain "
        f"transaction or cost any gas.\n"
        f"\n"
        f"URI: {uri}\n"
        f"Version: 1\n"
        f"Chain ID: {chain_id}\n"
        f"Nonce: {nonce}\n"
        f"Issued At: {issued}\n"
        f"Expiration Time: {expiration}"
    )


def _recover_eth_signer(message: str, signature: str) -> str:
    try:
        recovered = Account.recover_message(encode_defunct(text=message), signature=signature)
        return to_checksum_address(recovered)
    except Exception as exc:
        logger.info("Ethereum signature recover failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid wallet signature") from exc


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


def _user_schema(user: User) -> UserSchema:
    return UserSchema(
        id=user.id,
        email=user.email,
        username=user.username,
        email_verified=user.email_verified,
        created_at=user.created_at,
        is_admin=settings.is_admin_username(user.username),
    )


def _synthetic_eth_identity(address: str) -> tuple[str, str]:
    """Stable email + username for wallet-only accounts (no mailbox)."""
    compact = address.lower().removeprefix("0x")
    email = f"eth.{compact}@wallets.signalengine.app"
    username = f"eth_{compact[:8]}"
    return email, username


async def _get_or_create_eth_user(session: AsyncSession, address: str) -> User:
    result = await session.execute(
        select(WalletAccount).where(
            WalletAccount.chain == CHAIN_ETHEREUM,
            WalletAccount.address == address.lower(),
        )
    )
    link = result.scalar_one_or_none()
    if link is not None:
        user = await session.get(User, link.user_id)
        if user is None:
            raise HTTPException(status_code=500, detail="Wallet user missing")
        return user

    email, username = _synthetic_eth_identity(address)
    # Avoid username collisions (unlikely but cheap to handle)
    base_username = username
    for i in range(8):
        clash = await session.execute(select(User).where(User.username == username))
        if clash.scalar_one_or_none() is None:
            break
        username = f"{base_username}{i + 1}"
    else:
        username = f"eth_{secrets.token_hex(4)}"

    user = User(
        email=email,
        username=username,
        password_hash=hash_password(secrets.token_urlsafe(48)),
        email_verified_at=datetime.now(UTC),
    )
    session.add(user)
    await session.flush()
    session.add(
        WalletAccount(
            user_id=user.id,
            chain=CHAIN_ETHEREUM,
            address=address.lower(),
        )
    )
    await session.flush()
    return user


@router.post("/challenge", response_model=WalletChallengeResponse)
async def wallet_challenge(
    body: WalletChallengeRequest,
    session: AsyncSession = Depends(get_db),
) -> WalletChallengeResponse:
    """Issue a one-time SIWE-style message for the given address."""
    chain = body.chain.strip().lower()
    if chain != CHAIN_ETHEREUM:
        raise HTTPException(
            status_code=400,
            detail="Only ethereum is supported in this release (Solana/Sui coming next)",
        )
    address = _normalize_eth_address(body.address)
    nonce = secrets.token_hex(16)
    expires_at = datetime.now(UTC) + timedelta(minutes=CHALLENGE_TTL_MINUTES)
    message = _build_siwe_message(
        address=address,
        nonce=nonce,
        chain_id=body.chain_id,
        expires_at=expires_at,
    )
    session.add(
        WalletAuthChallenge(
            chain=CHAIN_ETHEREUM,
            address=address.lower(),
            nonce=nonce,
            message=message,
            expires_at=expires_at,
        )
    )
    await session.flush()
    return WalletChallengeResponse(
        chain=CHAIN_ETHEREUM,
        address=address,
        nonce=nonce,
        message=message,
        expires_at=expires_at,
    )


@router.post("/verify", response_model=UserSchema)
async def wallet_verify(
    body: WalletVerifyRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> UserSchema:
    """Verify signed challenge, create/link user, and set session cookie."""
    chain = body.chain.strip().lower()
    if chain != CHAIN_ETHEREUM:
        raise HTTPException(status_code=400, detail="Only ethereum is supported in this release")

    address = _normalize_eth_address(body.address)
    result = await session.execute(
        select(WalletAuthChallenge).where(
            WalletAuthChallenge.nonce == body.nonce.strip(),
            WalletAuthChallenge.chain == CHAIN_ETHEREUM,
            WalletAuthChallenge.address == address.lower(),
        )
    )
    challenge = result.scalar_one_or_none()
    if challenge is None:
        raise HTTPException(status_code=400, detail="Unknown or expired challenge")
    if challenge.consumed_at is not None:
        raise HTTPException(status_code=400, detail="Challenge already used")
    now = datetime.now(UTC)
    exp = challenge.expires_at if challenge.expires_at.tzinfo else challenge.expires_at.replace(tzinfo=UTC)
    if now > exp:
        raise HTTPException(status_code=400, detail="Challenge expired")

    recovered = _recover_eth_signer(challenge.message, body.signature.strip())
    if recovered.lower() != address.lower():
        raise HTTPException(status_code=401, detail="Signature does not match address")

    challenge.consumed_at = now
    user = await _get_or_create_eth_user(session, address)
    await session.flush()

    token = create_access_token(user.id)
    _set_session_cookie(response, token)
    return _user_schema(user)
