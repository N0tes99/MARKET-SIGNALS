"""Wallet public handles must not echo the address."""

from app.core.wallet_identity import random_wallet_username, synthetic_wallet_email


def test_eth_username_avoids_wallet_chars() -> None:
    address = "0x" + "a1b2c3d4" * 5
    name = random_wallet_username(address)
    assert 3 <= len(name) <= 8
    assert name.isalpha()
    assert set(name.lower()).isdisjoint({ch.lower() for ch in address if ch.isalnum()})
    assert address.lower().removeprefix("0x")[:8] not in name
    assert not name.startswith("eth")


def test_solana_username_avoids_wallet_chars() -> None:
    address = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
    name = random_wallet_username(address, taken={"mist", "reef"})
    assert set(name.lower()).isdisjoint({ch.lower() for ch in address if ch.isalnum()})
    assert name.lower() not in {"mist", "reef"}


def test_synthetic_email_is_handle_only() -> None:
    email = synthetic_wallet_email("wispqk")
    assert email == "wispqk@wallets.signalengine.app"
    assert "0x" not in email
