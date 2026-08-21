"""Generate strong random secrets for Signal Engine deploy and save locally.

Usage (from project root or anywhere):
  python scripts/generate_secrets.py

Writes secrets.local.env next to this file's project root (gitignored).
"""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_FILE = ROOT / "secrets.local.env"

ALPHANUM = string.ascii_letters + string.digits
# Password-safe (no quotes/spaces that break .env / shells)
PASSWORD_SAFE = string.ascii_letters + string.digits + "!@#%^&*-_=+"


def token_urlsafe(nbytes: int = 48) -> str:
    return secrets.token_urlsafe(nbytes)


def token_hex(nbytes: int = 32) -> str:
    return secrets.token_hex(nbytes)


def password(length: int = 32) -> str:
    return "".join(secrets.choice(PASSWORD_SAFE) for _ in range(length))


def main() -> None:
    secret_key = token_urlsafe(48)
    auth_password = password(32)
    extra_1 = token_hex(32)
    extra_2 = token_urlsafe(32)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    content = f"""# Generated {stamp} — DO NOT COMMIT (gitignored)
# Paste into Render / Netlify environment variables.

# Backend (Render Web Service)
SECRET_KEY={secret_key}
AUTH_USERNAME=signal
AUTH_PASSWORD={auth_password}
APP_ENV=production
APP_DEBUG=false
SIGNAL_STORE=postgres

# Optional spares
EXTRA_SECRET_1={extra_1}
EXTRA_SECRET_2={extra_2}

# Reminder: set DATABASE_URL from your host's Postgres dashboard (don't invent it).
# CORS_ORIGINS=https://your-site.netlify.app
"""

    OUT_FILE.write_text(content, encoding="utf-8")
    print(f"Wrote {OUT_FILE}")
    print()
    print("--- copy these ---")
    print(f"SECRET_KEY={secret_key}")
    print(f"AUTH_USERNAME=signal")
    print(f"AUTH_PASSWORD={auth_password}")
    print("---")
    print("Keep secrets.local.env private. It is gitignored.")


if __name__ == "__main__":
    main()
