"""Random-but-seeded novelty stamps for paper fills."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

# Verb · Adjective Noun  (desk-notary vibes, not spam)
_VERBS = (
    "SEALED",
    "NOTARIZED",
    "EMBOSSED",
    "WAXED",
    "RUBBER-STAMPED",
    "COUNTERSIGNED",
    "LAMINATED",
    "CERTIFIED",
)
_ADJECTIVES = (
    "Caffeinated",
    "Sentient",
    "Polite",
    "Midnight",
    "Leftover",
    "Velvety",
    "Unbothered",
    "Overqualified",
    "Slightly Damp",
    "Orbiting",
    "Complimentary",
    "Illegal-Adjacent",
    "Artisanal",
    "Retired",
    "Lucky",
    "Haunted",
)
_NOUNS = (
    "Raccoon",
    "Pretzel",
    "Comet",
    "Fax Machine",
    "Marshmallow",
    "Ladder",
    "Lotus",
    "Bagel",
    "Otter",
    "Telescope",
    "Waffle",
    "Pocket Watch",
    "Moth",
    "Trombone",
    "Pickle",
    "Satellite",
)
_OFFICES = (
    "Void Notary",
    "Moon Clerk",
    "Dip Bureau",
    "Alpha Post",
    "Chaos Customs",
    "The Bureau of Mild Alpha",
    "Desk 4¾",
    "Wax & Wicks Ltd.",
)
_BLURBS = (
    "Wax still warm. Do not lick the seal.",
    "Issued under the Treaty of Maybe.",
    "This stamp is biodegradable and slightly judgmental.",
    "Not financial advice. Barely stationery advice.",
    "Clerk initialed it twice. That means they meant it.",
    "Hologram flickers if you look too confident.",
    "Valid until the next candle, or boredom, whichever first.",
    "Filed next to the sandwich drawer.",
    "The raccoon in accounting signed off.",
    "Please keep this stub for your fictional records.",
    "Forged in a microwave. Legally binding in paper-land.",
    "If found, return to the paper desk. Do not sell.",
)
_RARITIES: tuple[tuple[str, int, int, str], ...] = (
    # name, weight, discord color, emoji
    ("Common", 50, 0x6B7280, "🎟️"),
    ("Uncommon", 28, 0x3D7A5A, "🌿"),
    ("Rare", 15, 0x3B6EA5, "💠"),
    ("Holo", 6, 0x8B5CF6, "✨"),
    ("Mythic", 1, 0xC9A227, "🏆"),
)


@dataclass(frozen=True)
class PaperStamp:
    """One minted paper-desk stamp."""

    title: str
    serial: str
    rarity: str
    emoji: str
    office: str
    blurb: str
    color: int

    @property
    def line(self) -> str:
        return f"{self.emoji} {self.title} · {self.rarity} · {self.serial}"


def mint_stamp(seed: str) -> PaperStamp:
    """Deterministic stamp from a trade id (same fill → same seal)."""
    digest = hashlib.sha256(seed.encode()).hexdigest()
    rng = random.Random(int(digest[:16], 16))
    verb = rng.choice(_VERBS)
    adj = rng.choice(_ADJECTIVES)
    noun = rng.choice(_NOUNS)
    office = rng.choice(_OFFICES)
    blurb = rng.choice(_BLURBS)
    rarity, color, emoji = _pick_rarity(rng)
    serial = f"SE-{digest[4:8].upper()}-{digest[20:22].upper()}"
    return PaperStamp(
        title=f"{verb} · {adj} {noun}",
        serial=serial,
        rarity=rarity,
        emoji=emoji,
        office=office,
        blurb=blurb,
        color=color,
    )


def _pick_rarity(rng: random.Random) -> tuple[str, int, str]:
    names, weights, colors, emojis = zip(*_RARITIES, strict=True)
    pick = rng.choices(list(names), weights=list(weights), k=1)[0]
    for name, _w, color, emoji in _RARITIES:
        if name == pick:
            return name, color, emoji
    return _RARITIES[0][0], _RARITIES[0][2], _RARITIES[0][3]


def paper_discord_payload(kind: str, trade, stamp: PaperStamp) -> tuple[str, dict, bytes]:
    """Discord content + embed + stamp PNG for a paper open or close."""
    from app.engines.paper_agent.stamp_art import STAMP_FILENAME, render_stamp_png

    direction = str(getattr(trade, "direction", "")).upper()
    symbol = str(getattr(trade, "symbol", "?"))
    setup = str(getattr(trade, "setup_type", ""))
    conf = float(getattr(trade, "confidence", 0.0))
    size = float(getattr(trade, "size_usd", 0.0))
    tp = float(getattr(trade, "take_profit_pct", 6.0))
    sl = float(getattr(trade, "stop_loss_pct", 3.0))
    entry = float(getattr(trade, "optimistic_entry", 0.0) or 0.0)

    body_kind = "open" if kind == "test" else kind
    if body_kind == "close":
        pnl = getattr(trade, "honest_pnl_usd", None)
        if pnl is None:
            pnl = getattr(trade, "optimistic_pnl_usd", None)
        ret = getattr(trade, "honest_return_pct", None)
        if ret is None:
            ret = getattr(trade, "optimistic_return_pct", None)
        reason = getattr(trade, "close_reason", "") or "done"
        verb = "VOIDED" if (pnl is not None and float(pnl) < 0) else "CLEARED"
        content = _content_line(f"PAPER {verb}", stamp)
        desc = f"{stamp.blurb}\n_{stamp.office}_"
        fields = [
            {"name": "Reason", "value": str(reason), "inline": True},
            {
                "name": "PnL",
                "value": (
                    f"${float(pnl):+.2f} ({float(ret):+.1f}%)"
                    if pnl is not None and ret is not None
                    else "—"
                ),
                "inline": True,
            },
            {"name": "Setup", "value": setup or "—", "inline": True},
        ]
        color = 0x8FA88A if pnl is not None and float(pnl) >= 0 else 0xA67C73
    else:
        label = "PAPER OPEN (TEST)" if kind == "test" else "PAPER OPEN"
        content = _content_line(label, stamp)
        desc = f"{stamp.blurb}\n_{stamp.office}_"
        fields = [
            {"name": "Side", "value": f"{direction} {symbol}", "inline": True},
            {"name": "Conf", "value": f"{conf:.0f}%", "inline": True},
            {"name": "Size", "value": f"${size:,.0f}", "inline": True},
            {"name": "Fill (opt)", "value": f"{entry:.6g}" if entry else "—", "inline": True},
            {"name": "ATR exits", "value": f"TP +{tp:.1f}% / SL −{sl:.1f}%", "inline": True},
            {"name": "Setup", "value": setup or "—", "inline": True},
        ]
        color = stamp.color

    png = render_stamp_png(
        stamp,
        symbol=symbol,
        direction=direction,
        kind="test" if kind == "test" else body_kind,
    )
    embed = {
        "title": f"{symbol} · {setup or 'paper'}",
        "description": desc,
        "color": color,
        "fields": fields,
        "footer": {"text": f"{stamp.office} · {stamp.serial} · paper desk"},
        "image": {"url": f"attachment://{STAMP_FILENAME}"},
    }
    return content, embed, png


def _content_line(kind: str, stamp: PaperStamp) -> str:
    return (
        f"**{kind}** {stamp.emoji} `{stamp.title}` · {stamp.rarity} · `{stamp.serial}`"
    )
