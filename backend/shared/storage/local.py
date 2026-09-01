"""
Local file storage — saves uploads to backend/uploads/<folder>/.
Will be replaced by R2 in Phase 1.
"""
from __future__ import annotations
import os
import uuid
import logging
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'ogg', 'aac', 'm4a', 'wav'}
ALLOWED_FILE_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_AUDIO_EXTENSIONS | {'pdf', 'doc', 'docx'}


def _content_matches_extension(data: bytes, ext: str) -> bool:
    """save_upload() previously trusted the client-supplied filename
    extension alone — a malicious file renamed to end in .jpg (or .pdf/.docx,
    both also allowed) sailed straight through onto disk, most sharply a
    risk on the KYC document/selfie upload where a human admin later opens
    whatever was submitted. This checks the actual bytes match what the
    extension claims, not exhaustively (not a full parser), enough to
    reject an outright mismatched file."""
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        try:
            from PIL import Image
            import io
            Image.open(io.BytesIO(data)).verify()
            return True
        except Exception:
            return False
    if ext == 'pdf':
        return data[:5] == b'%PDF-'
    if ext == 'docx':
        return data[:4] == b'PK\x03\x04'  # docx is a zip archive
    if ext == 'doc':
        return data[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'  # legacy OLE format
    return True  # audio formats: extension-only, low risk, not checked here


def _get_upload_folder():
    try:
        from flask import current_app
        return current_app.config.get('UPLOAD_FOLDER', 'uploads')
    except Exception:
        return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads')


def save_upload(file, folder: str = 'general') -> str | None:
    """
    Save an uploaded file to disk.
    Returns the relative URL path (e.g. /uploads/avatars/abc.jpg) or None on error.
    """
    if not file or not file.filename:
        return None

    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    if ext not in ALLOWED_FILE_EXTENSIONS:
        logger.warning(f'[Storage] Rejected file extension: {ext}')
        return None

    file_bytes = file.read()
    if not _content_matches_extension(file_bytes, ext):
        logger.warning(f'[Storage] File content did not match claimed extension: {ext}')
        return None

    upload_folder = _get_upload_folder()
    dest_dir = os.path.join(upload_folder, folder)
    os.makedirs(dest_dir, exist_ok=True)

    unique_name = f'{uuid.uuid4().hex}.{ext}'
    dest_path = os.path.join(dest_dir, unique_name)

    try:
        with open(dest_path, 'wb') as f:
            f.write(file_bytes)
        return f'/uploads/{folder}/{unique_name}'
    except Exception as exc:
        logger.error(f'[Storage] Failed to save file: {exc}')
        return None


def save_bytes(data: bytes, ext: str, folder: str = 'general') -> str | None:
    """Same as save_upload but for raw bytes with a known extension already
    validated by the caller (see url_fetch.py) — used for the drag-an-image-
    from-a-webpage flow, where there's no Werkzeug FileStorage object."""
    ext = (ext or '').lower().lstrip('.')
    if ext not in ALLOWED_FILE_EXTENSIONS:
        logger.warning(f'[Storage] Rejected file extension: {ext}')
        return None
    if not _content_matches_extension(data, ext):
        logger.warning(f'[Storage] File content did not match claimed extension: {ext}')
        return None

    upload_folder = _get_upload_folder()
    dest_dir = os.path.join(upload_folder, folder)
    os.makedirs(dest_dir, exist_ok=True)

    unique_name = f'{uuid.uuid4().hex}.{ext}'
    dest_path = os.path.join(dest_dir, unique_name)

    try:
        with open(dest_path, 'wb') as f:
            f.write(data)
        return f'/uploads/{folder}/{unique_name}'
    except Exception as exc:
        logger.error(f'[Storage] Failed to save bytes: {exc}')
        return None


def get_url(path: str | None) -> str | None:
    """Convert a stored path to a full URL."""
    if not path:
        return None
    try:
        from flask import current_app, request
        app_url = current_app.config.get('APP_URL', '')
        if app_url:
            return f"{app_url.rstrip('/')}{path}"
        return path
    except Exception:
        return path
