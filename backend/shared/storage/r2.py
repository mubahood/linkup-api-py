"""
Cloudflare R2 storage client — T-API-012.

Implements the same interface as local.py (save_upload, get_url) so
callers need zero changes when the backend is switched.

Strategy:
  1. If R2 credentials are configured (R2_ACCOUNT_ID, R2_ACCESS_KEY_ID,
     R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME), uploads go to R2 via the
     S3-compatible API (boto3).
  2. If credentials are missing (local dev), falls back to local.py
     transparently.

Environment variables needed for production:
  R2_ACCOUNT_ID       = <Cloudflare account ID>
  R2_ACCESS_KEY_ID    = <R2 API token key ID>
  R2_SECRET_ACCESS_KEY= <R2 API token secret>
  R2_BUCKET_NAME      = linkup-media          (or override)
  R2_PUBLIC_BASE_URL  = https://media.linkup.app  (CDN / public bucket URL)
"""
import os
import uuid
import logging
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'ogg', 'aac', 'm4a', 'wav'}
ALLOWED_FILE_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_AUDIO_EXTENSIONS | {'pdf', 'doc', 'docx'}


def _r2_client():
    """Return a boto3 S3 client pointing at R2, or None if not configured."""
    account_id = os.getenv('R2_ACCOUNT_ID', '')
    access_key  = os.getenv('R2_ACCESS_KEY_ID', '')
    secret_key  = os.getenv('R2_SECRET_ACCESS_KEY', '')
    if not (account_id and access_key and secret_key):
        return None
    try:
        import boto3
        return boto3.client(
            's3',
            endpoint_url=f'https://{account_id}.r2.cloudflarestorage.com',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name='auto',
        )
    except ImportError:
        logger.warning('[R2] boto3 not installed — falling back to local storage.')
        return None
    except Exception as e:
        logger.error(f'[R2] Client init failed: {e}')
        return None


def save_upload(file, folder: str = 'general') -> str | None:
    """
    Upload a file.
    Returns the public URL (R2 CDN) or a local path (fallback).
    """
    if not file or not file.filename:
        return None

    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in ALLOWED_FILE_EXTENSIONS:
        logger.warning(f'[Storage] Rejected file extension: {ext}')
        return None

    unique_name = f'{folder}/{uuid.uuid4().hex}.{ext}'

    client = _r2_client()
    if client:
        bucket = os.getenv('R2_BUCKET_NAME', 'linkup-media')
        try:
            file_bytes = file.read()
            content_type = _content_type(ext)
            client.put_object(
                Bucket=bucket,
                Key=unique_name,
                Body=file_bytes,
                ContentType=content_type,
            )
            base = os.getenv('R2_PUBLIC_BASE_URL', '').rstrip('/')
            if base:
                return f'{base}/{unique_name}'
            # Fallback: use R2 endpoint URL
            account_id = os.getenv('R2_ACCOUNT_ID', '')
            return f'https://{bucket}.{account_id}.r2.cloudflarestorage.com/{unique_name}'
        except Exception as e:
            logger.error(f'[R2] Upload failed: {e}')
            return None
    else:
        # Local fallback (dev mode)
        file.seek(0)
        from backend.shared.storage.local import save_upload as local_save
        return local_save(file, folder=folder)


def get_url(path: str | None) -> str | None:
    """Resolve a stored path/key to a full URL."""
    if not path:
        return None
    # Already a full URL
    if path.startswith('http://') or path.startswith('https://'):
        return path
    # Local path — prefix with APP_URL
    try:
        from flask import current_app
        app_url = current_app.config.get('APP_URL', '').rstrip('/')
        return f'{app_url}{path}' if app_url else path
    except Exception:
        return path


def _content_type(ext: str) -> str:
    return {
        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
        'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp',
        'pdf': 'application/pdf',
        'mp3': 'audio/mpeg', 'ogg': 'audio/ogg',
        'aac': 'audio/aac', 'm4a': 'audio/mp4', 'wav': 'audio/wav',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }.get(ext, 'application/octet-stream')
