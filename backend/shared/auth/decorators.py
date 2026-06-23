"""
LinkUp JWT Auth Decorators
Handles lu_accounts (new system) authentication.
"""
import json
import logging
from functools import wraps

from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

logger = logging.getLogger(__name__)


def _get_lu_account():
    """
    Get the current authenticated LU account.
    Supports: Bearer token, raw token in Authorization header.
    """
    try:
        verify_jwt_in_request()
        account_id = get_jwt_identity()
        # Import here to avoid circular imports
        from backend.domains.identity.models import Account
        from backend.models import db
        account = db.session.get(Account, account_id)
        return account
    except Exception as e:
        logger.debug(f"[LUAuth] JWT verification failed: {e}")
        return None


def _touch_last_seen(account) -> None:
    """
    Update last_seen_at at most once every 90 seconds per account.
    Kept lightweight: single UPDATE, no extra SELECT, silent on failure.
    This feeds the Active-Now graph and the AI interest-decay model.
    """
    from datetime import datetime, timedelta
    from backend.models import db
    now = datetime.utcnow()
    if account.last_seen_at and (now - account.last_seen_at) < timedelta(seconds=90):
        return
    try:
        account.last_seen_at = now
        db.session.commit()
    except Exception:
        db.session.rollback()


def lu_jwt_required(fn):
    """Decorator that provides the current LU account and silently tracks presence."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        account = _get_lu_account()
        if not account:
            return jsonify({'code': 0, 'message': 'Unauthorized'}), 401
        # Suspension check relaxed for now (dev) — accounts are not blocked by status.
        # if account.account_status != 'active':
        #     return jsonify({'code': 0, 'message': 'Account is suspended or closed'}), 403
        _touch_last_seen(account)
        return fn(account, *args, **kwargs)
    return wrapper


# Alias for backward compat with spec
jwt_required_with_user = lu_jwt_required


def sparks_mode_required(fn):
    """Decorator that requires sparks mode to be enabled on the account."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        account = _get_lu_account()
        if not account:
            return jsonify({'code': 0, 'message': 'Unauthorized'}), 401
        # Suspension check relaxed for now (dev) — accounts are not blocked by status.
        # if account.account_status != 'active':
        #     return jsonify({'code': 0, 'message': 'Account is suspended or closed'}), 403
        # Check modes_enabled (safe accessor — T-API-041)
        if not account.modes.get('sparks', False):
            return jsonify({'code': 0, 'message': 'Sparks mode is not enabled on your account'}), 403
        return fn(account, *args, **kwargs)
    return wrapper


def admin_required(fn):
    """Decorator for admin-only routes (uses old AdminUser system)."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            from backend.models.user import AdminUser
            from backend.models import db
            user = db.session.get(AdminUser, int(user_id))
        except Exception:
            user = None
        if not user:
            return jsonify({'code': 0, 'message': 'Unauthorized'}), 401
        if user.user_type not in ('Admin', 'Super Admin'):
            return jsonify({'code': 0, 'message': 'Admin access required'}), 403
        return fn(user, *args, **kwargs)
    return wrapper
