from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

out = Path(r"C:\Users\ognot\Projects\signal-engine\frontend\public")
out.mkdir(parents=True, exist_ok=True)
BG = (7, 7, 6, 255)
FG = (230, 226, 216, 255)
FG_DIM = (230, 226, 216, 140)


def make(size: int, *, radius_ratio: float = 0.18, pad_ratio: float = 0.0, filename: str) -> None:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = int(size * pad_ratio)
    r = max(8, int((size - 2 * margin) * radius_ratio))
    box = [margin, margin, size - margin - 1, size - margin - 1]
    draw.rounded_rectangle(box, radius=r, fill=BG)
    font_size = int(size * 0.38)
    font = None
    for name in [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]:
        try:
            font = ImageFont.truetype(name, font_size)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()
    text = "SE"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) / 2 - bbox[0]
    y = (size - th) / 2 - bbox[1] - size * 0.04
    draw.text((x, y), text, font=font, fill=FG)
    line_w = int(size * 0.22)
    line_h = max(2, int(size * 0.012))
    lx0 = (size - line_w) // 2
    ly = int(size * 0.68)
    draw.rectangle([lx0, ly, lx0 + line_w, ly + line_h], fill=FG_DIM)
    img.save(out / filename, "PNG")
    print("wrote", filename, size)


make(180, filename="apple-touch-icon.png", radius_ratio=0.2)
make(192, filename="icon-192.png", radius_ratio=0.2)
make(512, filename="icon-512.png", radius_ratio=0.19)
make(512, filename="icon-maskable-512.png", radius_ratio=0.22, pad_ratio=0.12)
print("done")
