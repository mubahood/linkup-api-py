"""
Auth utilities — supports both legacy AdminUser tokens and new lu_accounts JWT tokens.
"""
from functools import wraps
from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from backend.models import db
from backend.models.user import AdminUser


class _AccountWrapper:
    """
    Thin wrapper that makes an lu_accounts Account object duck-type
    compatible with AdminUser, so legacy routes can call user.user_type etc.
    """
    def __init__(self, account):
        self._account = account

    def __getattr__(self, name):
        # Delegate everything to the underlying Account
        return getattr(self._account, name)

    @property
    def user_type(self):
        # Map lu_accounts roles to legacy user_type values
        acct = self._account
        if getattr(acct, 'is_admin', False):
            return 'Admin'
        return 'Customer'


def get_current_user():
    """
    Resolve the current user from JWT identity.
    Handles two token kinds:
    - Legacy (integer): looks up AdminUser by int PK
    - New (UUID string): looks up lu_accounts Account by UUID
    Falls back to user_id query/body param for old mobile clients.
    """
    try:
        verify_jwt_in_request()
        identity = get_jwt_identity()
    except Exception:
        identity = None

    if identity:
        # Try new-style UUID first (lu_accounts)
        try:
            from backend.domains.identity.models import Account
            acct = Account.query.get(str(identity))
            if acct and acct.deleted_at is None:
                return _AccountWrapper(acct)
        except Exception:
            pass

        # Fall back to legacy AdminUser (integer PK)
        try:
            user = db.session.get(AdminUser, int(identity))
            if user:
                return user
        except (ValueError, TypeError):
            pass

    # Final fallback: user_id in request body / query string
    user_id = (
        request.form.get('user_id') or
        request.args.get('user_id') or
        (request.get_json(silent=True) or {}).get('user_id')
    )
    if user_id:
        try:
            return db.session.get(AdminUser, int(user_id))
        except (ValueError, TypeError):
            pass

    return None


def jwt_required_with_user(fn):
    """Decorator: provides current user to route. Handles legacy + new tokens."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'code': 0, 'message': 'Unauthorized'}), 401
        return fn(user, *args, **kwargs)
    return wrapper


def admin_required(fn):
    """Decorator: requires Admin user type."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'code': 0, 'message': 'Unauthorized'}), 401
        ut = getattr(user, 'user_type', None)
        if ut not in ('Admin', 'Super Admin'):
            return jsonify({'code': 0, 'message': 'Admin access required'}), 403
        return fn(user, *args, **kwargs)
    return wrapper
