"""Ethereum wallet challenge / verify unit tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.dependencies import get_db
from app.core.security import SESSION_COOKIE_NAME
from app.database.base import Base
from app.main import app
from app.models import User, WalletAccount  # noqa: F401
from app.api.routes.wallet_auth import _build_siwe_message, _normalize_eth_address


def test_normalize_eth_address_checksum() -> None:
    lower = "0x" + "a" * 40
    checksum = _normalize_eth_address(lower)
    assert checksum.startswith("0x")
    assert len(checksum) == 42


def test_siwe_message_contains_nonce_and_no_tx_copy() -> None:
    msg = _build_siwe_message(
        address="0x" + "b" * 40,
        nonce="abc123",
        chain_id=1,
        expires_at=datetime(2026, 8, 12, 12, 0, tzinfo=UTC),
    )
    assert "Nonce: abc123" in msg
    assert "will not trigger a blockchain transaction" in msg
    assert "Version: 1" in msg


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
    assert user["username"].startswith("eth_")
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

    # Replay nonce rejected
    replay = await client.post(
        "/api/v1/auth/wallet/verify",
        json={
            "chain": "ethereum",
            "address": address,
            "signature": signed.signature.hex(),
            "nonce": body["nonce"],
        },
    )
    assert replay.status_code == 400


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
async def test_wallet_rejects_solana_chain(wallet_client) -> None:
    client, _ = wallet_client
    res = await client.post(
        "/api/v1/auth/wallet/challenge",
        json={"chain": "solana", "address": "0x" + "c" * 40, "chain_id": 1},
    )
    assert res.status_code == 400
