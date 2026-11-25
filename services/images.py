"""Ridimensionamento immagini e generazione QR PNG."""

from __future__ import annotations

from io import BytesIO

import segno
from PIL import Image, ImageOps, UnidentifiedImageError

from core.errors.media_errors import http_error_invalid_image

AVATAR_SIZE = 512
COVER_MAX_EDGE = 1920
QR_SCALE = 8
QR_BORDER = 2

_OUTPUT_FORMAT = "WEBP"
_WEBP_QUALITY = 85


def process_avatar(data: bytes) -> bytes:
    """Crop quadrato al centro, max 512px, WebP."""
    image = _open_rgb(data)
    image = ImageOps.fit(
        image,
        (AVATAR_SIZE, AVATAR_SIZE),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    return _to_webp(image)


def process_cover(data: bytes) -> bytes:
    """Ridimensiona il lato lungo a 1920px, WebP (niente crop)."""
    image = _open_rgb(data)
    image.thumbnail((COVER_MAX_EDGE, COVER_MAX_EDGE), Image.Resampling.LANCZOS)
    return _to_webp(image)


def render_qr_png(payload: str) -> bytes:
    """PNG del QR (per email / Gmail)."""
    qr = segno.make(payload, error="m")
    buffer = BytesIO()
    qr.save(buffer, kind="png", scale=QR_SCALE, border=QR_BORDER)
    return buffer.getvalue()


def _open_rgb(data: bytes) -> Image.Image:
    if not data:
        raise http_error_invalid_image()
    try:
        image = Image.open(BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise http_error_invalid_image() from exc
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        alpha = image.getchannel("A") if "A" in image.getbands() else None
        background.paste(image.convert("RGB"), mask=alpha)
        return background
    return image.convert("RGB")


def _to_webp(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format=_OUTPUT_FORMAT, quality=_WEBP_QUALITY, method=6)
    return buffer.getvalue()
