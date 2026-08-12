"""Procedural wax-seal cards for paper Discord stamps."""

from __future__ import annotations

import hashlib
import io
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.engines.paper_agent.stamps import PaperStamp

STAMP_FILENAME = "paper-stamp.png"
_W, _H = 720, 960

_PALETTES: dict[str, dict[str, tuple[int, int, int]]] = {
    "Common": {
        "bg": (24, 26, 30),
        "paper": (36, 38, 44),
        "ink": (214, 216, 220),
        "accent": (154, 158, 166),
        "seal": (96, 100, 108),
        "wax": (72, 76, 84),
    },
    "Uncommon": {
        "bg": (12, 28, 24),
        "paper": (18, 40, 34),
        "ink": (210, 236, 220),
        "accent": (88, 176, 132),
        "seal": (48, 120, 88),
        "wax": (28, 86, 62),
    },
    "Rare": {
        "bg": (12, 22, 40),
        "paper": (18, 32, 56),
        "ink": (214, 228, 248),
        "accent": (96, 156, 220),
        "seal": (48, 92, 168),
        "wax": (28, 58, 120),
    },
    "Holo": {
        "bg": (22, 12, 36),
        "paper": (36, 20, 58),
        "ink": (238, 226, 255),
        "accent": (196, 120, 255),
        "seal": (140, 72, 210),
        "wax": (88, 36, 150),
    },
    "Mythic": {
        "bg": (16, 12, 6),
        "paper": (32, 24, 10),
        "ink": (255, 226, 150),
        "accent": (220, 168, 56),
        "seal": (176, 122, 32),
        "wax": (120, 78, 18),
    },
}


def render_stamp_png(
    stamp: PaperStamp,
    *,
    symbol: str = "",
    direction: str = "",
    kind: str = "open",
) -> bytes:
    """Paint a unique 720×960 card; same stamp seed always reprints."""
    rng = random.Random(int(hashlib.sha256(stamp.serial.encode()).hexdigest()[:16], 16))
    pal = _PALETTES.get(stamp.rarity, _PALETTES["Common"])
    img = Image.new("RGB", (_W, _H), pal["bg"])
    draw = ImageDraw.Draw(img)
    _paper_grain(img, rng, pal)
    margin = 36
    draw.rounded_rectangle(
        (margin, margin, _W - margin, _H - margin),
        radius=28,
        fill=pal["paper"],
        outline=pal["accent"],
        width=4,
    )
    draw.rounded_rectangle(
        (margin + 14, margin + 14, _W - margin - 14, _H - margin - 14),
        radius=18,
        outline=pal["ink"],
        width=1,
    )
    _perforations(draw, pal["accent"])
    banner = _banner(kind)
    title_font = _font(28)
    body_font = _font(22)
    small_font = _font(18)
    tiny_font = _font(15)
    draw.text((60, 64), "SIGNAL ENGINE  ·  PAPER DESK", fill=pal["accent"], font=tiny_font)
    draw.text((60, 96), banner, fill=pal["ink"], font=title_font)
    draw.text((60, 138), stamp.rarity.upper(), fill=pal["accent"], font=small_font)
    _wax_seal(draw, rng, pal, cx=_W // 2, cy=390)
    verb, _, rest = stamp.title.partition(" · ")
    draw.text((60, 640), verb, fill=pal["accent"], font=small_font)
    name = rest or stamp.title
    draw.text((60, 672), _fit(draw, name, body_font, _W - 120), fill=pal["ink"], font=body_font)
    office = _fit(draw, stamp.office, small_font, _W - 120)
    draw.text((60, 714), office, fill=pal["accent"], font=small_font)
    _barcode(draw, stamp.serial, pal["ink"], y=780)
    draw.text((60, 848), stamp.serial, fill=pal["ink"], font=small_font)
    meta = "  ·  ".join(p for p in (symbol.upper(), direction.upper(), stamp.rarity) if p)
    draw.text((60, 884), meta or stamp.serial, fill=pal["accent"], font=tiny_font)
    if stamp.rarity in {"Holo", "Mythic"}:
        img = _sheen(img, pal["accent"], rng)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _banner(kind: str) -> str:
    if kind == "close":
        return "CLEARED / VOIDED"
    if kind == "test":
        return "TEST PRINT"
    return "ISSUED"


def _paper_grain(img: Image.Image, rng: random.Random, pal: dict) -> None:
    pixels = img.load()
    w, h = img.size
    for _ in range(4200):
        x = rng.randint(0, w - 1)
        y = rng.randint(0, h - 1)
        d = rng.randint(-10, 10)
        r, g, b = pal["bg"]
        pixels[x, y] = (max(0, r + d), max(0, g + d), max(0, b + d))


def _perforations(draw: ImageDraw.ImageDraw, color: tuple[int, int, int]) -> None:
    for x in range(56, _W - 56, 14):
        draw.ellipse((x, 48, x + 5, 53), fill=color)
        draw.ellipse((x, _H - 53, x + 5, _H - 48), fill=color)
    for y in range(56, _H - 56, 14):
        draw.ellipse((48, y, 53, y + 5), fill=color)
        draw.ellipse((_W - 53, y, _W - 48, y + 5), fill=color)


def _wax_seal(
    draw: ImageDraw.ImageDraw,
    rng: random.Random,
    pal: dict,
    *,
    cx: int,
    cy: int,
) -> None:
    spikes = 9 + rng.randint(0, 10)
    outer = 168
    inner = 78
    pts = []
    for i in range(spikes * 2):
        ang = (math.pi * 2 * i) / (spikes * 2) + rng.random() * 0.08
        rad = outer if i % 2 == 0 else outer - 36 - rng.randint(0, 18)
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    draw.polygon(pts, fill=pal["wax"], outline=pal["accent"])
    draw.ellipse((cx - 132, cy - 132, cx + 132, cy + 132), outline=pal["ink"], width=3)
    rings = 3 + rng.randint(0, 3)
    for i in range(rings):
        r = inner + i * 18
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=pal["accent"], width=1)
    rays = 8 + rng.randint(0, 8)
    for i in range(rays):
        ang = (math.pi * 2 * i) / rays + rng.random() * 0.2
        x2 = cx + int((outer - 24) * math.cos(ang))
        y2 = cy + int((outer - 24) * math.sin(ang))
        draw.line((cx, cy, x2, y2), fill=pal["seal"], width=2)
    draw.ellipse(
        (cx - 36, cy - 36, cx + 36, cy + 36),
        fill=pal["seal"],
        outline=pal["ink"],
        width=2,
    )
    # inner monogram
    draw.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), fill=pal["ink"])


def _barcode(
    draw: ImageDraw.ImageDraw,
    serial: str,
    color: tuple[int, int, int],
    *,
    y: int,
) -> None:
    x = 60
    digest = hashlib.sha256(serial.encode()).digest()
    for bit in digest[:28]:
        width = 2 if bit % 3 else 4
        height = 28 if bit % 2 else 38
        draw.rectangle((x, y, x + width, y + height), fill=color)
        x += width + 3


def _sheen(img: Image.Image, accent: tuple[int, int, int], rng: random.Random) -> Image.Image:
    import numpy as np

    w, h = img.size
    ys = np.linspace(0, 1, h, dtype=np.float32)
    phase = rng.random() * math.pi
    shade = 0.12 + 0.22 * np.abs(np.sin(ys * math.pi * 2 + phase))
    overlay = np.zeros((h, w, 3), dtype=np.float32)
    overlay[..., 0] = accent[0] * shade[:, None]
    overlay[..., 1] = accent[1] * shade[:, None]
    overlay[..., 2] = accent[2] * shade[:, None]
    base = np.asarray(img, dtype=np.float32)
    mixed = np.clip(base * (1 - 0.22) + overlay * 0.22, 0, 255).astype(np.uint8)
    return Image.fromarray(mixed, "RGB")


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        Path(r"C:\Windows\Fonts\georgia.ttf"),
        Path(r"C:\Windows\Fonts\calibri.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _fit(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    while len(text) > 3 and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text + "…"
