"""Validate and downscale chart screenshots before vision analysis."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_EDGE_PX = 1280
MAX_PIXELS = 25_000_000
ALLOWED_MIME = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})

_FORMAT_TO_MIME = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "GIF": "image/png",
}


@dataclass(frozen=True)
class PreparedImage:
    """Normalized screenshot bytes ready for a vision model."""

    data: bytes
    mime: str
    width: int
    height: int


class ImageRejected(ValueError):
    """User-facing validation failure for an uploaded screenshot."""


def prepare_chart_image(data: bytes, content_type: str | None) -> PreparedImage:
    """Decode, bound, and optionally downscale a chart screenshot.

    GIFs are flattened to PNG (first frame). Output is JPEG or PNG.
    """
    if not data:
        raise ImageRejected("Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImageRejected("Image too large (max 8MB)")

    mime = (content_type or "").split(";")[0].strip().lower()
    if mime and mime not in ALLOWED_MIME and mime != "application/octet-stream":
        raise ImageRejected("Use a PNG, JPEG, WebP, or GIF screenshot")

    previous_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        try:
            image = Image.open(BytesIO(data))
            image.load()
        except UnidentifiedImageError as exc:
            raise ImageRejected("File is not a readable image") from exc
        except Image.DecompressionBombError as exc:
            raise ImageRejected("Image is too large to analyze") from exc
    finally:
        Image.MAX_IMAGE_PIXELS = previous_limit

    source_format = (image.format or "").upper()
    image = ImageOps.exif_transpose(image)
    if image.mode != "RGB":
        image = image.convert("RGB")

    width, height = image.size
    if width < 32 or height < 32:
        raise ImageRejected("Image is too small to read as a chart")

    longest = max(width, height)
    if longest > MAX_EDGE_PX:
        scale = MAX_EDGE_PX / longest
        image = image.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.Resampling.LANCZOS,
        )
        width, height = image.size

    # JPEG is smaller over the wire; Groq vision does not need lossless PNG.
    prefer_jpeg = source_format in {"JPEG", "JPG", "WEBP"} or longest > MAX_EDGE_PX
    out_format = "JPEG" if prefer_jpeg else "PNG"
    buf = BytesIO()
    save_kwargs: dict[str, object] = {"optimize": True}
    if out_format == "JPEG":
        save_kwargs["quality"] = 78
        if image.mode != "RGB":
            image = image.convert("RGB")
    image.save(buf, format=out_format, **save_kwargs)
    encoded = buf.getvalue()
    if len(encoded) > MAX_UPLOAD_BYTES:
        raise ImageRejected("Image too large after processing (max 8MB)")

    return PreparedImage(
        data=encoded,
        mime=_FORMAT_TO_MIME[out_format],
        width=width,
        height=height,
    )
