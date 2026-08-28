"""
Server-side image compression — every photo that reaches storage, whether
a local upload or a URL fetch (see url_fetch.py), goes through here first.

No new dependency: Pillow already ships (url_fetch.py already uses it for
image validation). The win is entirely in the recipe, not the library:
  - fix orientation from the EXIF tag phone cameras set instead of
    physically rotating pixels (skip this and a sideways photo stays
    sideways forever, since nothing else in this pipeline looks at EXIF)
  - cap resolution to something no surface in this app ever displays a
    photo larger than — a 4000px phone-camera original buys nothing over
    1920px on any admin console or mobile screen, at 4-8x the file size
  - re-encode as WebP, which balances quality/size automatically and, for
    photographic content, comes out 25-50% smaller than JPEG at
    equivalent visual quality — a hand-tuned JPEG quality setting can't
    beat that without also hand-tuning per image
"""
from __future__ import annotations
import io
import logging

logger = logging.getLogger(__name__)

MAX_DIMENSION = 1920  # long edge, in px
WEBP_QUALITY = 85     # visually near-lossless for photographic content
_FORMAT_TO_EXT = {'JPEG': 'jpg', 'PNG': 'png', 'GIF': 'gif', 'WEBP': 'webp', 'BMP': 'bmp', 'TIFF': 'tiff'}


def compress_image(data: bytes) -> tuple[bytes, str]:
    """Re-encode arbitrary image bytes as a smaller WebP.

    Returns (compressed_bytes, 'webp') — or, on the rare input where
    re-encoding doesn't actually shrink it (a tiny or already-optimal
    image), the original bytes and its own format's extension, so this
    step can never make a file bigger than what came in.

    Raises ValueError if `data` isn't a genuine, decodable image. Callers
    that accept uploads from outside this process (see url_fetch.py) should
    already have checked that, but this is the last line of defense before
    anything touches disk/R2 — a spoofed extension or Content-Type alone
    can't get non-image bytes stored.
    """
    from PIL import Image, ImageOps

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as e:
        raise ValueError(f'Not a valid image: {e}')

    original_format = (img.format or 'JPEG').upper()

    # exif_transpose returns a new image with rotation baked into the
    # pixels and the orientation tag cleared — must happen before resizing
    # or a photo shot in portrait gets cropped/scaled as if it were landscape.
    img = ImageOps.exif_transpose(img)

    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGBA' if 'A' in img.getbands() else 'RGB')

    if max(img.size) > MAX_DIMENSION:
        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, 'WEBP', quality=WEBP_QUALITY, method=6)
    compressed = buf.getvalue()

    if len(compressed) < len(data):
        return compressed, 'webp'

    logger.info('[image_compress] WebP re-encode was not smaller (%d >= %d bytes) — keeping original',
                len(compressed), len(data))
    return data, _FORMAT_TO_EXT.get(original_format, 'jpg')
