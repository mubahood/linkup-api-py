"""
Local file storage — saves uploads to backend/uploads/<folder>/.
Will be replaced by R2 in Phase 1.
"""
import os
import uuid
import logging
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'ogg', 'aac', 'm4a', 'wav'}
ALLOWED_FILE_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_AUDIO_EXTENSIONS | {'pdf', 'doc', 'docx'}


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

    upload_folder = _get_upload_folder()
    dest_dir = os.path.join(upload_folder, folder)
    os.makedirs(dest_dir, exist_ok=True)

    unique_name = f'{uuid.uuid4().hex}.{ext}'
    dest_path = os.path.join(dest_dir, unique_name)

    try:
        file.save(dest_path)
        return f'/uploads/{folder}/{unique_name}'
    except Exception as exc:
        logger.error(f'[Storage] Failed to save file: {exc}')
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
