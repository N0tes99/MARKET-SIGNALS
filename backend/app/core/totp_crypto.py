"""Encrypt per-user TOTP secrets at rest.

TOTP codes are truncated HMACs of a time counter. The authenticator secret is
the HMAC key — storing it plaintext in Postgres would let anyone with a DB dump
generate valid codes. Secrets are sealed with XSalsa20-Poly1305 (PyNaCl
SecretBox) keyed from SECRET_KEY. Legacy plaintext rows still verify and are
rewritten encrypted on the next successful unlock.
"""

from __future__ import annotations

import hashlib
from base64 import urlsafe_b64decode, urlsafe_b64encode

from nacl.exceptions import CryptoError
from nacl.secret import SecretBox

from app.config import settings

_PREFIX = "enc:v1:"


def _box() -> SecretBox:
    material = f"se-totp-at-rest-v1:{settings.secret_key}".encode()
    return SecretBox(hashlib.sha256(material).digest())


def is_encrypted_totp_secret(stored: str | None) -> bool:
    return bool(stored) and stored.startswith(_PREFIX)


def encrypt_totp_secret(plain: str) -> str:
    raw = (plain or "").strip().replace(" ", "")
    if not raw:
        raise ValueError("empty totp secret")
    token = _box().encrypt(raw.encode("ascii"))
    return _PREFIX + urlsafe_b64encode(bytes(token)).decode("ascii")


def decrypt_totp_secret(stored: str | None) -> str | None:
    """Return the authenticator secret, or None if missing/undecryptable."""
    if not stored:
        return None
    value = stored.strip()
    if not value:
        return None
    if value.startswith(_PREFIX):
        try:
            blob_b64 = value[len(_PREFIX):]
            pad = "=" * ((4 - len(blob_b64) % 4) % 4)
            blob = urlsafe_b64decode(blob_b64 + pad)
            plain = _box().decrypt(blob).decode("ascii")
        except (CryptoError, ValueError, UnicodeDecodeError):
            return None
        cleaned = plain.strip().replace(" ", "")
        return cleaned or None
    if value.startswith("enc:"):
        return None
    return value.replace(" ", "") or None
