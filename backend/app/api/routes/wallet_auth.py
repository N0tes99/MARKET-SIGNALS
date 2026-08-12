"""Multi-chain wallet message-sign login (Ethereum, Solana, Sui)."""

from __future__ import annotations

import base64
import hashlib
import logging
import re
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import base58
import nacl.signing
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
from app.core.wallet_identity import random_wallet_username, synthetic_wallet_email
from app.models.user import User
from app.models.wallet import WalletAccount, WalletAuthChallenge
from app.schemas.auth import UserSchema

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wallet")

CHAIN_ETHEREUM = "ethereum"
CHAIN_SOLANA = "solana"
CHAIN_SUI = "sui"
SUPPORTED_CHAINS = {CHAIN_ETHEREUM, CHAIN_SOLANA, CHAIN_SUI}
CHALLENGE_TTL_MINUTES = 10

_ETH_ADDR_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_SUI_ADDR_RE = re.compile(r"^0x[a-fA-F0-9]{1,64}$")


class WalletChallengeRequest(BaseModel):
    chain: str = Field(default=CHAIN_ETHEREUM, max_length=32)
    address: str = Field(min_length=32, max_length=128)
    chain_id: int = Field(default=1, ge=1)


class WalletChallengeResponse(BaseModel):
    chain: str
    address: str
    nonce: str
    message: str
    expires_at: datetime


class WalletVerifyRequest(BaseModel):
    chain: str = Field(default=CHAIN_ETHEREUM, max_length=32)
    address: str = Field(min_length=32, max_length=128)
    signature: str = Field(min_length=8, max_length=512)
    nonce: str = Field(min_length=8, max_length=64)


def _app_domain() -> str:
    base = settings.resolved_public_app_url().rstrip("/")
    host = urlparse(base).hostname
    return host or "localhost"


def _build_login_message(
    *, chain: str, address: str, nonce: str, chain_id: int, expires_at: datetime
) -> str:
    domain = _app_domain()
    uri = settings.resolved_public_app_url().rstrip("/")
    issued = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    expiration = expires_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    label = {"ethereum": "Ethereum", "solana": "Solana", "sui": "Sui"}[chain]
    lines = [
        f"{domain} wants you to sign in with your {label} account:",
        address,
        "",
        "Sign in to Signal Engine. This request will not trigger a blockchain "
        "transaction or cost any gas/fees.",
        "",
        f"URI: {uri}",
        "Version: 1",
        f"Chain: {chain}",
    ]
    if chain == CHAIN_ETHEREUM:
        lines.append(f"Chain ID: {chain_id}")
    lines.extend(
        [
            f"Nonce: {nonce}",
            f"Issued At: {issued}",
            f"Expiration Time: {expiration}",
        ]
    )
    return "\n".join(lines)


def _normalize_eth_address(address: str) -> str:
    raw = address.strip()
    if not _ETH_ADDR_RE.match(raw) or not is_address(raw):
        raise HTTPException(status_code=400, detail="Invalid Ethereum address")
    return to_checksum_address(raw)


def _normalize_solana_address(address: str) -> str:
    raw = address.strip()
    try:
        decoded = base58.b58decode(raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid Solana address") from exc
    if len(decoded) != 32:
        raise HTTPException(status_code=400, detail="Invalid Solana address length")
    return raw


def _normalize_sui_address(address: str) -> str:
    raw = address.strip().lower()
    if not raw.startswith("0x"):
        raw = f"0x{raw}"
    if not _SUI_ADDR_RE.match(raw):
        raise HTTPException(status_code=400, detail="Invalid Sui address")
    hex_part = raw[2:]
    if len(hex_part) > 64:
        raise HTTPException(status_code=400, detail="Invalid Sui address length")
    return "0x" + hex_part.zfill(64)


def _normalize_address(chain: str, address: str) -> str:
    if chain == CHAIN_ETHEREUM:
        return _normalize_eth_address(address)
    if chain == CHAIN_SOLANA:
        return _normalize_solana_address(address)
    if chain == CHAIN_SUI:
        return _normalize_sui_address(address)
    raise HTTPException(status_code=400, detail="Unsupported chain")


def _storage_address(chain: str, address: str) -> str:
    if chain == CHAIN_SOLANA:
        return address  # base58 is case-sensitive
    return address.lower()


def _recover_eth_signer(message: str, signature: str) -> str:
    try:
        recovered = Account.recover_message(encode_defunct(text=message), signature=signature)
        return to_checksum_address(recovered)
    except Exception as exc:
        logger.info("Ethereum signature recover failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid wallet signature") from exc


def _verify_solana_signature(*, address: str, message: str, signature: str) -> None:
    try:
        pubkey = base58.b58decode(address)
        if signature.startswith("0x"):
            sig_bytes = bytes.fromhex(signature[2:])
        else:
            try:
                sig_bytes = base58.b58decode(signature)
            except Exception:
                sig_bytes = base64.b64decode(signature)
        if len(sig_bytes) == 64:
            pass
        elif len(sig_bytes) > 64:
            # Some wallets return pubkey||sig or similar — take last 64
            sig_bytes = sig_bytes[-64:]
        else:
            raise ValueError("bad signature length")
        nacl.signing.VerifyKey(pubkey).verify(message.encode("utf-8"), sig_bytes)
    except HTTPException:
        raise
    except Exception as exc:
        logger.info("Solana signature verify failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid Solana signature") from exc


def _uleb128(n: int) -> bytes:
    out = bytearray()
    while True:
        byte = n & 0x7F
        n >>= 7
        out.append(byte | 0x80 if n else byte)
        if not n:
            break
    return bytes(out)


def _sui_personal_message_digest(message: bytes) -> bytes:
    """Blake2b-256 of IntentMessage(PersonalMessage) BCS bytes."""
    bcs_msg = _uleb128(len(message)) + message
    intent_message = bytes([3, 0, 0]) + bcs_msg
    return hashlib.blake2b(intent_message, digest_size=32).digest()


def _sui_address_from_ed25519_pubkey(pubkey: bytes) -> str:
    digest = hashlib.blake2b(bytes([0x00]) + pubkey, digest_size=32).digest()
    return "0x" + digest.hex()


def _verify_sui_signature(*, address: str, message: str, signature: str) -> None:
    """Accept Sui serialized sig ``flag||sig||pk`` (base64), as returned by Phantom."""
    try:
        raw = base64.b64decode(signature)
        # Some wallets wrap as JSON — rare but cheap to try.
        if raw[:1] == b"{":
            import json

            parsed = json.loads(raw.decode("utf-8"))
            if isinstance(parsed, dict) and "signature" in parsed:
                raw = base64.b64decode(parsed["signature"])
        if len(raw) < 1 + 64 + 32:
            raise ValueError("signature too short")
        flag = raw[0]
        if flag != 0x00:
            raise ValueError(f"unsupported Sui scheme flag {flag}")
        sig = raw[1:65]
        pubkey = raw[65:97]
        derived = _sui_address_from_ed25519_pubkey(pubkey)
        if derived != _normalize_sui_address(address):
            raise ValueError("address does not match public key")
        digest = _sui_personal_message_digest(message.encode("utf-8"))
        nacl.signing.VerifyKey(pubkey).verify(digest, sig)
    except HTTPException:
        raise
    except Exception as exc:
        logger.info("Sui signature verify failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid Sui signature") from exc


def _verify_signature(*, chain: str, address: str, message: str, signature: str) -> None:
    if chain == CHAIN_ETHEREUM:
        recovered = _recover_eth_signer(message, signature.strip())
        if recovered.lower() != address.lower():
            raise HTTPException(status_code=401, detail="Signature does not match address")
        return
    if chain == CHAIN_SOLANA:
        _verify_solana_signature(address=address, message=message, signature=signature.strip())
        return
    if chain == CHAIN_SUI:
        _verify_sui_signature(address=address, message=message, signature=signature.strip())
        return
    raise HTTPException(status_code=400, detail="Unsupported chain")


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


async def _taken_usernames(session: AsyncSession) -> set[str]:
    rows = await session.execute(select(User.username))
    return {name.lower() for name in rows.scalars().all() if name}


async def _get_or_create_wallet_user(
    session: AsyncSession,
    *,
    chain: str,
    address: str,
) -> User:
    stored = _storage_address(chain, address)
    result = await session.execute(
        select(WalletAccount).where(
            WalletAccount.chain == chain,
            WalletAccount.address == stored,
        )
    )
    link = result.scalar_one_or_none()
    if link is not None:
        user = await session.get(User, link.user_id)
        if user is None:
            raise HTTPException(status_code=500, detail="Wallet user missing")
        return user

    try:
        username = random_wallet_username(address, taken=await _taken_usernames(session))
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="Could not assign username") from exc
    email = synthetic_wallet_email(username)

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
            chain=chain,
            address=stored,
        )
    )
    await session.flush()
    return user


@router.post("/challenge", response_model=WalletChallengeResponse)
async def wallet_challenge(
    body: WalletChallengeRequest,
    session: AsyncSession = Depends(get_db),
) -> WalletChallengeResponse:
    """Issue a one-time login message for ETH / Solana / Sui."""
    chain = body.chain.strip().lower()
    if chain not in SUPPORTED_CHAINS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported chain. Use ethereum, solana, or sui.",
        )
    address = _normalize_address(chain, body.address)
    nonce = secrets.token_hex(16)
    expires_at = datetime.now(UTC) + timedelta(minutes=CHALLENGE_TTL_MINUTES)
    message = _build_login_message(
        chain=chain,
        address=address,
        nonce=nonce,
        chain_id=body.chain_id,
        expires_at=expires_at,
    )
    session.add(
        WalletAuthChallenge(
            chain=chain,
            address=_storage_address(chain, address),
            nonce=nonce,
            message=message,
            expires_at=expires_at,
        )
    )
    await session.flush()
    return WalletChallengeResponse(
        chain=chain,
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
    if chain not in SUPPORTED_CHAINS:
        raise HTTPException(status_code=400, detail="Unsupported chain")

    address = _normalize_address(chain, body.address)
    stored = _storage_address(chain, address)
    result = await session.execute(
        select(WalletAuthChallenge).where(
            WalletAuthChallenge.nonce == body.nonce.strip(),
            WalletAuthChallenge.chain == chain,
            WalletAuthChallenge.address == stored,
        )
    )
    challenge = result.scalar_one_or_none()
    if challenge is None:
        raise HTTPException(status_code=400, detail="Unknown or expired challenge")
    if challenge.consumed_at is not None:
        raise HTTPException(status_code=400, detail="Challenge already used")
    now = datetime.now(UTC)
    exp = (
        challenge.expires_at
        if challenge.expires_at.tzinfo
        else challenge.expires_at.replace(tzinfo=UTC)
    )
    if now > exp:
        raise HTTPException(status_code=400, detail="Challenge expired")

    _verify_signature(
        chain=chain,
        address=address,
        message=challenge.message,
        signature=body.signature,
    )

    challenge.consumed_at = now
    user = await _get_or_create_wallet_user(session, chain=chain, address=address)
    await session.flush()

    token = create_access_token(user.id)
    _set_session_cookie(response, token)
    return _user_schema(user)
