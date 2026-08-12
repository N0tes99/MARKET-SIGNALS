"""Multi-chain wallet challenge / verify tests."""

from __future__ import annotations

import base64
from datetime import UTC, datetime

import base58
import nacl.signing
import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.conftest import _test_admin_user

from app.api.routes.wallet_auth import (
    _build_login_message,
    _normalize_eth_address,
    _sui_address_from_ed25519_pubkey,
    _sui_personal_message_digest,
    _verify_solana_signature,
    _verify_sui_signature,
)
from app.config import settings
from app.core.auth_deps import require_admin_user
from app.core.dependencies import get_db
from app.core.security import SESSION_COOKIE_NAME
from app.database.base import Base
from app.main import app
from app.models import User, WalletAccount  # noqa: F401


def test_normalize_eth_address_checksum() -> None:
    lower = "0x" + "a" * 40
    checksum = _normalize_eth_address(lower)
    assert checksum.startswith("0x")
    assert len(checksum) == 42


def test_login_message_mentions_no_tx() -> None:
    msg = _build_login_message(
        chain="solana",
        address="So11anaAddr",
        nonce="abc123",
        chain_id=1,
        expires_at=datetime(2026, 8, 12, 12, 0, tzinfo=UTC),
    )
    assert "Nonce: abc123" in msg
    assert "will not trigger a blockchain" in msg
    assert "Chain: solana" in msg


def test_solana_signature_roundtrip() -> None:
    sk = nacl.signing.SigningKey.generate()
    address = base58.b58encode(bytes(sk.verify_key)).decode()
    message = "sign-in Solana"
    signed = sk.sign(message.encode("utf-8"))
    signature = base58.b58encode(signed.signature).decode()
    _verify_solana_signature(address=address, message=message, signature=signature)


def test_sui_signature_roundtrip() -> None:
    sk = nacl.signing.SigningKey.generate()
    pubkey = bytes(sk.verify_key)
    address = _sui_address_from_ed25519_pubkey(pubkey)
    message = "sign-in Sui"
    digest = _sui_personal_message_digest(message.encode("utf-8"))
    signed = sk.sign(digest)
    payload = bytes([0x00]) + signed.signature + pubkey
    signature = base64.b64encode(payload).decode()
    _verify_sui_signature(address=address, message=message, signature=signature)


async def _postgres_available() -> bool:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


@pytest.fixture
async def wallet_client():
    if not await _postgres_available():
        pytest.skip("Postgres not available")

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, factory
    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


@pytest.mark.asyncio
async def test_wallet_challenge_and_verify_roundtrip(wallet_client) -> None:
    client, factory = wallet_client
    acct = Account.create()
    address = acct.address

    challenge = await client.post(
        "/api/v1/auth/wallet/challenge",
        json={"chain": "ethereum", "address": address, "chain_id": 1},
    )
    assert challenge.status_code == 200
    body = challenge.json()
    assert body["address"] == address
    assert body["nonce"]
    assert "Sign in to Signal Engine" in body["message"]

    signed = acct.sign_message(encode_defunct(text=body["message"]))
    signature = signed.signature.hex()
    if not signature.startswith("0x"):
        signature = f"0x{signature}"
    verify = await client.post(
        "/api/v1/auth/wallet/verify",
        json={
            "chain": "ethereum",
            "address": address,
            "signature": signature,
            "nonce": body["nonce"],
        },
    )
    assert verify.status_code == 200
    user = verify.json()
    handle = user["username"]
    assert 3 <= len(handle) <= 8
    assert handle.isalpha()
    assert set(handle.lower()).isdisjoint({ch.lower() for ch in address if ch.isalnum()})
    assert address.lower().removeprefix("0x") not in handle.lower()
    assert "@" not in handle
    assert SESSION_COOKIE_NAME in verify.cookies

    async with factory() as session:
        rows = await session.execute(select(WalletAccount))
        links = list(rows.scalars())
        assert len(links) == 1
        assert links[0].address == address.lower()
        assert links[0].chain == "ethereum"
        db_user = await session.get(User, links[0].user_id)
        assert db_user is not None
        assert db_user.email_verified_at is not None
        assert db_user.username == handle
        assert address.lower().removeprefix("0x") not in db_user.email.lower()
        assert db_user.email.endswith("@wallets.signalengine.app")

    replay = await client.post(
        "/api/v1/auth/wallet/verify",
        json={
            "chain": "ethereum",
            "address": address,
            "signature": signature,
            "nonce": body["nonce"],
        },
    )
    assert replay.status_code == 400


@pytest.mark.asyncio
async def test_solana_challenge_and_verify_roundtrip(wallet_client) -> None:
    client, factory = wallet_client
    sk = nacl.signing.SigningKey.generate()
    address = base58.b58encode(bytes(sk.verify_key)).decode()

    challenge = await client.post(
        "/api/v1/auth/wallet/challenge",
        json={"chain": "solana", "address": address},
    )
    assert challenge.status_code == 200
    body = challenge.json()
    signed = sk.sign(body["message"].encode("utf-8"))
    signature = base58.b58encode(signed.signature).decode()
    verify = await client.post(
        "/api/v1/auth/wallet/verify",
        json={
            "chain": "solana",
            "address": address,
            "signature": signature,
            "nonce": body["nonce"],
        },
    )
    assert verify.status_code == 200
    handle = verify.json()["username"]
    assert set(handle.lower()).isdisjoint({ch.lower() for ch in address if ch.isalnum()})

    async with factory() as session:
        rows = await session.execute(
            select(WalletAccount).where(WalletAccount.chain == "solana")
        )
        assert rows.scalar_one().address == address


@pytest.mark.asyncio
async def test_sui_challenge_and_verify_roundtrip(wallet_client) -> None:
    client, factory = wallet_client
    sk = nacl.signing.SigningKey.generate()
    pubkey = bytes(sk.verify_key)
    address = _sui_address_from_ed25519_pubkey(pubkey)

    challenge = await client.post(
        "/api/v1/auth/wallet/challenge",
        json={"chain": "sui", "address": address},
    )
    assert challenge.status_code == 200
    body = challenge.json()
    digest = _sui_personal_message_digest(body["message"].encode("utf-8"))
    signed = sk.sign(digest)
    signature = base64.b64encode(bytes([0x00]) + signed.signature + pubkey).decode()
    verify = await client.post(
        "/api/v1/auth/wallet/verify",
        json={
            "chain": "sui",
            "address": address,
            "signature": signature,
            "nonce": body["nonce"],
        },
    )
    assert verify.status_code == 200
    handle = verify.json()["username"]
    assert set(handle.lower()).isdisjoint({ch.lower() for ch in address if ch.isalnum()})

    async with factory() as session:
        rows = await session.execute(select(WalletAccount).where(WalletAccount.chain == "sui"))
        assert rows.scalar_one().address == address.lower()


@pytest.mark.asyncio
async def test_wallet_verify_rejects_wrong_signer(wallet_client) -> None:
    client, _factory = wallet_client
    owner = Account.create()
    attacker = Account.create()

    challenge = await client.post(
        "/api/v1/auth/wallet/challenge",
        json={"chain": "ethereum", "address": owner.address, "chain_id": 1},
    )
    body = challenge.json()
    forged = attacker.sign_message(encode_defunct(text=body["message"]))
    verify = await client.post(
        "/api/v1/auth/wallet/verify",
        json={
            "chain": "ethereum",
            "address": owner.address,
            "signature": forged.signature.hex(),
            "nonce": body["nonce"],
        },
    )
    assert verify.status_code == 401


@pytest.mark.asyncio
async def test_admin_wallet_inbox_shows_address(wallet_client) -> None:
    client, _factory = wallet_client
    acct = Account.create()
    address = acct.address
    challenge = await client.post(
        "/api/v1/auth/wallet/challenge",
        json={"chain": "ethereum", "address": address, "chain_id": 1},
    )
    body = challenge.json()
    signed = acct.sign_message(encode_defunct(text=body["message"]))
    signature = signed.signature.hex()
    if not signature.startswith("0x"):
        signature = f"0x{signature}"
    verify = await client.post(
        "/api/v1/auth/wallet/verify",
        json={
            "chain": "ethereum",
            "address": address,
            "signature": signature,
            "nonce": body["nonce"],
        },
    )
    assert verify.status_code == 200
    handle = verify.json()["username"]

    app.dependency_overrides[require_admin_user] = _test_admin_user
    try:
        inbox = await client.get("/api/v1/auth/access/wallets")
    finally:
        app.dependency_overrides.pop(require_admin_user, None)

    assert inbox.status_code == 200
    rows = inbox.json()
    assert len(rows) == 1
    assert rows[0]["username"] == handle
    assert rows[0]["address"] == address.lower()
    assert rows[0]["chain"] == "ethereum"
    assert rows[0]["granted"] is False


@pytest.mark.asyncio
async def test_wallet_rejects_unknown_chain(wallet_client) -> None:
    client, _ = wallet_client
    res = await client.post(
        "/api/v1/auth/wallet/challenge",
        json={"chain": "bitcoin", "address": "0x" + "c" * 40, "chain_id": 1},
    )
    assert res.status_code == 400
