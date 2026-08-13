"""Rasterize the header SignalMark onto homescreen PNG icons."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

PUBLIC = Path(__file__).resolve().parents[1] / "public"
BG = (6, 9, 12, 255)
INK = (230, 226, 216, 255)
INK55 = (230, 226, 216, 140)

OUTER = [(20, 3.5), (38, 20.5), (33.6, 24.2), (20, 11.2), (6.4, 24.2), (2, 20.5)]
MID = [(20, 9), (32, 20), (28.4, 23.2), (20, 14.6), (11.6, 23.2), (8, 20)]
CORE = [(20, 14), (25.4, 22.5), (21.5, 22.5), (20, 19.8), (18.5, 22.5), (14.6, 22.5)]
BASE = [(12, 36), (28, 36), (20, 31.6)]


def _xy(pts: list[tuple[float, float]], scale: float, ox: float, oy: float) -> list[tuple[float, float]]:
    return [(x * scale + ox, y * scale + oy) for x, y in pts]


def render(size: int, *, inset: float) -> Image.Image:
    """Draw the 40×40 mark into a square canvas. ``inset`` is edge padding 0–0.5."""
    mult = 4
    wide = size * mult
    img = Image.new("RGBA", (wide, wide), BG)
    draw = ImageDraw.Draw(img, "RGBA")
    pad = wide * inset
    scale = (wide - 2 * pad) / 40.0
    ox = oy = pad

    draw.polygon(_xy(OUTER, scale, ox, oy), fill=INK55)
    draw.polygon(_xy(MID, scale, ox, oy), fill=INK55)
    draw.polygon(_xy(CORE, scale, ox, oy), fill=INK)
    draw.rectangle(
        [
            18.6 * scale + ox,
            21.5 * scale + oy,
            21.4 * scale + ox,
            33.0 * scale + oy,
        ],
        fill=INK,
    )
    draw.polygon(_xy(BASE, scale, ox, oy), fill=INK)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    PUBLIC.mkdir(parents=True, exist_ok=True)
    render(180, inset=0.14).save(PUBLIC / "apple-touch-icon.png", "PNG")
    render(192, inset=0.14).save(PUBLIC / "icon-192.png", "PNG")
    render(512, inset=0.14).save(PUBLIC / "icon-512.png", "PNG")
    render(512, inset=0.22).save(PUBLIC / "icon-maskable-512.png", "PNG")
    print("wrote", PUBLIC)


if __name__ == "__main__":
    main()
