"""
LinkUp Admin API — Phase 0 stub.
Full admin console rebuilt in T-API-036 (Phase 3).
Retained: member management, dashboard stats, system health.
"""
from datetime import datetime
from flask import Blueprint, request
from sqlalchemy import func, or_
from backend.models import db
from backend.models.user import AdminUser
from backend.models.payment import Payment
from backend.models.transaction import Transaction
from backend.models.user_wallet import UserWallet
from backend.utils.auth import admin_required
from backend.utils.response import success_response, error_response

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/api/admin/dashboard', methods=['GET'])
@admin_required
def dashboard(user):
    total_members = AdminUser.query.filter(AdminUser.deleted_at.is_(None)).count()
    active_members = AdminUser.query.filter(
        AdminUser.status == '1', AdminUser.deleted_at.is_(None)
    ).count()
    total_payments = Payment.query.count()
    total_revenue = db.session.query(func.sum(Payment.amount)).scalar() or 0
    return success_response("Dashboard loaded", {
        'total_members': total_members,
        'active_members': active_members,
        'total_payments': total_payments,
        'total_revenue': float(total_revenue),
    })


def _account_to_admin_dict(a):
    """Map lu_accounts → shape UsersPage.jsx expects."""
    modes = a.modes  # safe accessor (T-API-041)

    if a.is_admin:
        utype = 'Admin'
    elif a.is_premium:
        utype = 'Premium'
    else:
        utype = 'Member'

    return {
        'id': a.id,
        'name': a.display_name,
        'email': a.email or '',
        'phone_number': a.phone or '',
        'username': a.handle or '',
        'user_type': utype,
        'status': '1' if a.account_status == 'active' else '0',
        'avatar': a.avatar,
        'kyc_level': a.kyc_level,
        'is_premium': 'Yes' if a.is_premium else 'No',
        'is_admin': bool(a.is_admin),
        'modes_enabled': modes,
        'created_at': a.created_at.isoformat() if a.created_at else None,
    }


@admin_bp.route('/api/admin/users', methods=['GET'])
@admin_required
def users_index(user):
    from backend.domains.identity.models import Account

    page     = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search   = request.args.get('search', '')
    utype    = request.args.get('user_type', '')
    status   = request.args.get('status', '')

    q = Account.query.filter(Account.deleted_at.is_(None))

    if search:
        term = f'%{search}%'
        q = q.filter(or_(
            Account.display_name.ilike(term),
            Account.email.ilike(term),
            Account.phone.ilike(term),
            Account.handle.ilike(term),
        ))
    if utype == 'Admin':
        q = q.filter(Account.is_admin == 1)
    elif utype in ('Premium', 'Admins'):
        q = q.filter(Account.is_premium == 1)
    elif utype in ('Customers', 'Customer'):
        q = q.filter(Account.is_admin == 0)

    if status == '1':
        q = q.filter(Account.account_status == 'active')
    elif status == '0':
        q = q.filter(Account.account_status != 'active')

    pagination = q.order_by(Account.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return success_response("Members loaded", {
        'data': [_account_to_admin_dict(a) for a in pagination.items],
        'total': pagination.total,
        'current_page': pagination.page,
        'last_page': pagination.pages,
        'per_page': per_page,
    })


def _get_account(uid):
    from backend.domains.identity.models import Account
    # uid may be a UUID string or legacy integer — try both
    return (Account.query.filter_by(id=str(uid)).filter(Account.deleted_at.is_(None)).first()
            or Account.query.filter_by(id=uid).first())


@admin_bp.route('/api/admin/users/<user_id>', methods=['GET'])
@admin_required
def users_show(user, user_id):
    target = _get_account(user_id)
    if not target:
        return error_response("Member not found", status_code=404)
    data = _account_to_admin_dict(target)
    data['wallet'] = None  # wallet v2 lives in lu_wallets
    return success_response("Member loaded", data)


@admin_bp.route('/api/admin/users/<user_id>/update', methods=['POST', 'PUT'])
@admin_required
def users_update(user, user_id):
    target = _get_account(user_id)
    if not target:
        return error_response("Member not found", status_code=404)
    data = request.get_json() or {}
    # Map frontend field names → lu_accounts field names
    if 'name' in data:         target.display_name   = data['name']
    if 'email' in data:        target.email          = data['email']
    if 'phone_number' in data: target.phone          = data['phone_number']
    if 'username' in data:     target.handle         = data['username']
    if 'status' in data:
        target.account_status = 'active' if str(data['status']) == '1' else 'suspended'
    if 'user_type' in data and data['user_type'] == 'Admin':
        target.is_admin = 1
    db.session.commit()
    return success_response("Member updated", _account_to_admin_dict(target))


@admin_bp.route('/api/admin/users/<user_id>/reset-password', methods=['POST'])
@admin_required
def users_reset_password(user, user_id):
    import bcrypt
    target = _get_account(user_id)
    if not target:
        return error_response("Member not found", status_code=404)
    data = request.get_json() or {}
    new_password = data.get('new_password', '111111')
    target.password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    db.session.commit()
    return success_response("Password reset successfully")


@admin_bp.route('/api/admin/users/<user_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_status(user, user_id):
    target = _get_account(user_id)
    if not target:
        return error_response("Member not found", status_code=404)
    target.account_status = 'suspended' if target.account_status == 'active' else 'active'
    db.session.commit()
    new_status = '1' if target.account_status == 'active' else '0'
    return success_response("Status updated", {'status': new_status})


@admin_bp.route('/api/admin/users/<user_id>/delete', methods=['POST', 'DELETE'])
@admin_required
def users_delete(user, user_id):
    target = _get_account(user_id)
    if not target:
        return error_response("Member not found", status_code=404)
    target.deleted_at = datetime.utcnow()
    target.account_status = 'closed'
    db.session.commit()
    return success_response("Member deleted")


@admin_bp.route('/api/admin/users/<user_id>/wallet', methods=['GET'])
@admin_required
def users_wallet(user, user_id):
    # Wallet data lives in lu_wallets for v1 accounts
    return success_response("Wallet loaded", {'wallet': None, 'transactions': []})


@admin_bp.route('/api/admin/system/health', methods=['GET'])
@admin_required
def system_health(user):
    try:
        db.session.execute(db.text('SELECT 1'))
        db_status = 'ok'
    except Exception as e:
        db_status = f'error: {str(e)}'
    return success_response("Health check", {
        'api': 'ok',
        'database': db_status,
        'version': '1.0.0',
        'phase': 'Phase 0 — Rebrand & Foundation',
    })


@admin_bp.route('/api/admin/auth/login', methods=['POST'])
def admin_login():
    from flask_jwt_extended import create_access_token
    import bcrypt
    data = request.get_json() or {}
    identifier = data.get('email') or data.get('username') or data.get('phone_number')
    password = data.get('password', '')
    if not identifier or not password:
        return error_response("Email and password required", status_code=400)
    user = AdminUser.query.filter(
        or_(AdminUser.email == identifier, AdminUser.username == identifier,
            AdminUser.phone_number == identifier),
        AdminUser.deleted_at.is_(None)
    ).first()
    if not user:
        return error_response("Invalid credentials", status_code=401)
    pw_bytes = password.encode('utf-8')
    stored = user.password.replace('$2y$', '$2b$').encode('utf-8')
    if not bcrypt.checkpw(pw_bytes, stored):
        return error_response("Invalid credentials", status_code=401)
    if user.user_type != 'Admin':
        return error_response("Admin access required", status_code=403)
    token = create_access_token(identity=str(user.id))
    return success_response("Login successful", {'token': token, 'user': user.to_dict()})
