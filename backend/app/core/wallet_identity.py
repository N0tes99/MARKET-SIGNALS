"""Public handle for wallet signups — short, random, no wallet characters."""

from __future__ import annotations

import secrets
import string

# Short nature words. Filtered per-address so leftover letters never echo the wallet.
_WORDS = (
    "mist",
    "reef",
    "oak",
    "pine",
    "dusk",
    "lark",
    "kite",
    "plum",
    "vine",
    "wren",
    "silk",
    "moon",
    "knot",
    "wolf",
    "rosy",
    "grim",
    "zoom",
    "lily",
    "glow",
    "pink",
    "iris",
    "wisp",
    "lilt",
    "myth",
    "hymn",
    "nori",
    "yolk",
    "pony",
    "snow",
    "twin",
    "gust",
    "kelp",
    "moss",
    "rust",
    "soot",
    "tide",
    "foam",
    "cove",
    "bay",
    "fog",
)

_LETTERS = string.ascii_lowercase


def banned_chars(address: str) -> set[str]:
    return {ch.lower() for ch in address if ch.isalnum()}


def safe_alphabet(address: str) -> str:
    banned = banned_chars(address)
    return "".join(ch for ch in _LETTERS if ch not in banned)


def _name_ok(name: str, address: str) -> bool:
    if len(name) < 3 or len(name) > 8:
        return False
    if not name.isalpha() or not name.islower():
        return False
    return banned_chars(name).isdisjoint(banned_chars(address))


def random_wallet_username(address: str, *, taken: set[str] | None = None) -> str:
    """3–8 letter handle that shares no alphanumeric chars with ``address``."""
    used = {n.lower() for n in (taken or set())}
    banned = banned_chars(address)
    words = [w for w in _WORDS if banned.isdisjoint(set(w))]
    alphabet = safe_alphabet(address)
    if len(alphabet) < 3 and not words:
        raise ValueError("not enough leftover letters for a wallet username")

    for _ in range(64):
        if words:
            name = secrets.choice(words)
            extra = 2 if len(name) <= 4 and len(alphabet) >= 2 else 0
            if extra and len(name) + extra <= 8:
                name += "".join(secrets.choice(alphabet) for _ in range(extra))
        else:
            n = 5 if len(alphabet) >= 5 else max(3, len(alphabet))
            name = "".join(secrets.choice(alphabet) for _ in range(n))
        if name.lower() in used:
            continue
        if _name_ok(name, address):
            return name
    raise ValueError("could not mint a wallet username")


def synthetic_wallet_email(username: str) -> str:
    return f"{username.lower()}@wallets.signalengine.app"
