"""
Fetch an image from an arbitrary URL, safely — powers "drag an image from
another website" in the admin console (an admin drags a picture straight
from a browser tab; the browser only hands us the image's URL, not its
bytes, so the server has to go get it).

Fetching a URL the caller supplies is a classic SSRF vector: without
guards, an admin session (or anything that can reach this endpoint) could
make the server request internal services, cloud metadata endpoints
(169.254.169.254), etc. Every step here exists specifically to close one
of those doors:
  - scheme allowlist (http/https only — no file://, gopher://, etc.)
  - hostname resolved and every resulting IP checked against private /
    loopback / link-local / reserved / multicast ranges before connecting
  - redirects followed manually (not by `requests`) so each hop gets the
    same host/IP validation — a server can't pass the initial check and
    then 302 somewhere internal
  - response size capped while streaming, not just checked after download
  - content sniffed and decoded with Pillow — a spoofed Content-Type
    header alone can't get a non-image saved and served back out
"""
from __future__ import annotations
import ipaddress
import io
import logging
import socket
from urllib.parse import urlparse, urljoin

import requests

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 12 * 1024 * 1024  # 12 MB
FETCH_TIMEOUT = 8  # seconds, connect+read each hop
MAX_REDIRECTS = 4
ALLOWED_SCHEMES = {'http', 'https'}
# Pillow format -> our on-disk extension (see storage/local.py & r2.py)
_FORMAT_EXT = {'JPEG': 'jpg', 'PNG': 'png', 'GIF': 'gif', 'WEBP': 'webp'}

_UA = 'Mozilla/5.0 (compatible; AbanoonyaAdminBot/1.0; +https://abanoonyapro.online)'


class ImageFetchError(Exception):
    """Raised with a message safe to show an admin directly."""


def _is_public_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or
        ip.is_reserved or ip.is_multicast or ip.is_unspecified
    )


def _assert_safe_host(url: str) -> None:
    """Raises ImageFetchError unless every IP the hostname resolves to is a
    public, routable address. Called again on every redirect hop."""
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ImageFetchError(f'Unsupported URL scheme: {parsed.scheme or "(none)"}. Use an http(s) image URL.')
    if not parsed.hostname:
        raise ImageFetchError('That URL has no host.')

    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        raise ImageFetchError(f'Could not resolve host: {parsed.hostname}')

    resolved_ips = {info[4][0] for info in infos}
    if not resolved_ips or not all(_is_public_ip(ip) for ip in resolved_ips):
        logger.warning(f'[url_fetch] blocked non-public host {parsed.hostname!r} -> {resolved_ips}')
        raise ImageFetchError('That URL points to a private or internal address and can\'t be used.')


def fetch_image_from_url(url: str) -> tuple[bytes, str]:
    """Download and validate an image from `url`.

    Returns (image_bytes, extension) — extension is one of jpg/png/gif/webp,
    derived from the actual decoded image, never trusted from the URL or
    response headers alone.

    Raises ImageFetchError with an admin-facing message on any failure —
    callers should catch this and return it as the API error response.
    """
    if not url or not isinstance(url, str):
        raise ImageFetchError('No image URL provided.')
    url = url.strip()

    current_url = url
    for hop in range(MAX_REDIRECTS + 1):
        _assert_safe_host(current_url)
        try:
            resp = requests.get(
                current_url, stream=True, timeout=FETCH_TIMEOUT, allow_redirects=False,
                headers={'User-Agent': _UA, 'Accept': 'image/*'},
            )
        except requests.exceptions.RequestException as e:
            raise ImageFetchError(f'Could not reach that URL ({e.__class__.__name__}).')

        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get('Location')
            resp.close()
            if not location:
                raise ImageFetchError('That URL redirected without a destination.')
            current_url = urljoin(current_url, location)
            continue

        if resp.status_code != 200:
            resp.close()
            raise ImageFetchError(f'That URL returned HTTP {resp.status_code}.')

        content_type = (resp.headers.get('Content-Type') or '').split(';')[0].strip().lower()
        if content_type and not content_type.startswith('image/'):
            resp.close()
            raise ImageFetchError(f'That URL is not an image (Content-Type: {content_type or "unknown"}).')

        declared_length = resp.headers.get('Content-Length')
        if declared_length and declared_length.isdigit() and int(declared_length) > MAX_IMAGE_BYTES:
            resp.close()
            raise ImageFetchError(f'Image is too large (max {MAX_IMAGE_BYTES // (1024 * 1024)} MB).')

        buf = io.BytesIO()
        total = 0
        try:
            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_IMAGE_BYTES:
                    raise ImageFetchError(f'Image is too large (max {MAX_IMAGE_BYTES // (1024 * 1024)} MB).')
                buf.write(chunk)
        finally:
            resp.close()

        data = buf.getvalue()
        if not data:
            raise ImageFetchError('That URL returned an empty response.')

        try:
            from PIL import Image
            probe = Image.open(io.BytesIO(data))
            probe.verify()
            # verify() invalidates the handle for further use — reopen to
            # read the format for real.
            fmt = Image.open(io.BytesIO(data)).format
        except Exception:
            raise ImageFetchError('That URL is not a valid, readable image.')

        ext = _FORMAT_EXT.get(fmt or '')
        if not ext:
            raise ImageFetchError(f'Unsupported image format: {fmt or "unknown"}. Use JPG, PNG, GIF, or WebP.')

        return data, ext

    raise ImageFetchError('Too many redirects.')
