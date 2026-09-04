"""TOTP secrets are sealed at rest; HMAC codes from other keys cannot unlock."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pyotp
import pytest

from app.core.security import JWT_ALGORITHM, create_access_token
from app.core.site_gate import (
    _ensure_pending_secret,
    _upgrade_plaintext_totp_secret,
    create_mfa_token,
    decode_mfa_token,
    verify_user_totp,
)
from app.core.totp_crypto import (
    decrypt_totp_secret,
    encrypt_totp_secret,
    is_encrypted_totp_secret,
)
from app.models.user import User


def _user() -> User:
    return User(
        email="mfa@test.local",
        username="mfa_user",
        password_hash="not-a-real-hash",
    )


def test_totp_secret_roundtrip_is_sealed() -> None:
    plain = pyotp.random_base32()
    sealed = encrypt_totp_secret(plain)
    assert sealed.startswith("enc:v1:")
    assert plain not in sealed
    assert decrypt_totp_secret(sealed) == plain
    assert is_encrypted_totp_secret(sealed)


def test_legacy_plaintext_totp_secret_still_reads() -> None:
    plain = pyotp.random_base32()
    assert decrypt_totp_secret(plain) == plain
    assert not is_encrypted_totp_secret(plain)


def test_wrong_secret_key_cannot_decrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    plain = pyotp.random_base32()
    sealed = encrypt_totp_secret(plain)
    monkeypatch.setattr("app.core.totp_crypto.settings.secret_key", "attacker-other-key")
    assert decrypt_totp_secret(sealed) is None


def test_encrypted_blob_is_not_a_totp_hmac_key() -> None:
    """A DB dump of enc:v1:… cannot be fed to pyotp to mint the user's codes."""
    plain = pyotp.random_base32()
    sealed = encrypt_totp_secret(plain)
    user_code = pyotp.TOTP(plain).now()
    try:
        blob_code = pyotp.TOTP(sealed).now()
    except Exception:
        blob_code = None
    assert blob_code != user_code


def test_enroll_stores_encrypted_secret_not_plain() -> None:
    user = _user()
    plain = _ensure_pending_secret(user)
    assert pyotp.TOTP(plain).now()
    assert is_encrypted_totp_secret(user.totp_secret)
    assert plain not in (user.totp_secret or "")
    assert decrypt_totp_secret(user.totp_secret) == plain


def test_user_totp_accepts_own_code() -> None:
    user = _user()
    plain = _ensure_pending_secret(user)
    code = pyotp.TOTP(plain).now()
    step = verify_user_totp(user, code)
    assert step is not None


def test_site_secret_hmac_does_not_unlock_user(monkeypatch: pytest.MonkeyPatch) -> None:
    site = pyotp.random_base32()
    monkeypatch.setattr("app.core.site_gate.settings.site_totp_secret", site)
    monkeypatch.setattr("app.config.settings.site_totp_secret", site)
    user = _user()
    plain = _ensure_pending_secret(user)
    site_code = pyotp.TOTP(site).now()
    user_code = pyotp.TOTP(plain).now()
    if site_code == user_code:
        pytest.skip("site and user TOTP codes collided this window")
    assert verify_user_totp(user, site_code) is None
    assert verify_user_totp(user, user_code) is not None


def test_replayed_totp_code_is_rejected() -> None:
    user = _user()
    plain = _ensure_pending_secret(user)
    code = pyotp.TOTP(plain).now()
    step = verify_user_totp(user, code)
    assert step is not None
    user.totp_last_step = step
    assert verify_user_totp(user, code) is None


def test_legacy_plaintext_row_verifies_and_upgrades() -> None:
    user = _user()
    plain = pyotp.random_base32()
    user.totp_secret = plain
    code = pyotp.TOTP(plain).now()
    assert verify_user_totp(user, code) is not None
    _upgrade_plaintext_totp_secret(user)
    assert is_encrypted_totp_secret(user.totp_secret)
    assert decrypt_totp_secret(user.totp_secret) == plain


def test_mfa_jwt_requires_bound_user() -> None:
    uid = uuid4()
    token = create_mfa_token(
        user_id=uid, grant_expires_at=datetime.now(UTC) + timedelta(hours=1)
    )
    assert decode_mfa_token(token, user_id=uid)
    assert not decode_mfa_token(token)
    assert not decode_mfa_token(token, user_id=uuid4())


def test_session_jwt_cannot_be_used_as_mfa() -> None:
    uid = uuid4()
    session = create_access_token(uid)
    assert not decode_mfa_token(session, user_id=uid)


def test_mfa_jwt_signed_with_wrong_key_is_rejected() -> None:
    uid = uuid4()
    token = jwt.encode(
        {
            "typ": "site_mfa",
            "sub": str(uid),
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
        },
        "attacker-generated-key",
        algorithm=JWT_ALGORITHM,
    )
    assert not decode_mfa_token(token, user_id=uid)


def test_unsigned_alg_none_mfa_jwt_is_rejected() -> None:
    import json
    from base64 import urlsafe_b64encode

    uid = uuid4()
    exp = int((datetime.now(UTC) + timedelta(hours=1)).timestamp())

    def _b64(data: dict) -> str:
        raw = json.dumps(data, separators=(",", ":")).encode()
        return urlsafe_b64encode(raw).decode().rstrip("=")

    token = (
        f"{_b64({'alg': 'none', 'typ': 'JWT'})}."
        f"{_b64({'typ': 'site_mfa', 'sub': str(uid), 'exp': exp})}."
    )
    assert not decode_mfa_token(token, user_id=uid)


def test_tampered_mfa_signature_is_rejected() -> None:
    uid = uuid4()
    token = create_mfa_token(
        user_id=uid, grant_expires_at=datetime.now(UTC) + timedelta(hours=1)
    )
    header, payload, sig = token.split(".")
    flipped = "A" if not sig.startswith("A") else "B"
    tampered = f"{header}.{payload}.{flipped}{sig[1:]}"
    assert not decode_mfa_token(tampered, user_id=uid)
