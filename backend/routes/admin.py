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


@admin_bp.route('/api/admin/users', methods=['GET'])
@admin_required
def users_index(user):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '')
    user_type = request.args.get('user_type', '')
    status = request.args.get('status', '')

    q = AdminUser.query.filter(AdminUser.deleted_at.is_(None))
    if search:
        term = f'%{search}%'
        q = q.filter(or_(
            AdminUser.name.ilike(term),
            AdminUser.email.ilike(term),
            AdminUser.phone_number.ilike(term),
            AdminUser.username.ilike(term),
        ))
    if user_type:
        q = q.filter(AdminUser.user_type == user_type)
    if status:
        q = q.filter(AdminUser.status == status)

    pagination = q.order_by(AdminUser.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return success_response("Members loaded", {
        'data': [u.to_dict() for u in pagination.items],
        'total': pagination.total,
        'current_page': pagination.page,
        'last_page': pagination.pages,
        'per_page': per_page,
    })


@admin_bp.route('/api/admin/users/<int:user_id>', methods=['GET'])
@admin_required
def users_show(user, user_id):
    target = AdminUser.query.get(user_id)
    if not target:
        return error_response("Member not found", status_code=404)
    user_data = target.to_dict()
    wallet = UserWallet.query.filter_by(user_id=user_id).first()
    user_data['wallet'] = wallet.to_dict() if wallet else None
    return success_response("Member loaded", user_data)


@admin_bp.route('/api/admin/users/<int:user_id>/update', methods=['POST', 'PUT'])
@admin_required
def users_update(user, user_id):
    target = AdminUser.query.get(user_id)
    if not target:
        return error_response("Member not found", status_code=404)
    data = request.get_json() or {}
    for field in ['name', 'first_name', 'last_name', 'email', 'phone_number', 'user_type', 'status']:
        if field in data:
            setattr(target, field, data[field])
    target.updated_at = datetime.utcnow()
    db.session.commit()
    return success_response("Member updated", target.to_dict())


@admin_bp.route('/api/admin/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def users_reset_password(user, user_id):
    import bcrypt
    target = AdminUser.query.get(user_id)
    if not target:
        return error_response("Member not found", status_code=404)
    data = request.get_json() or {}
    new_password = data.get('new_password', 'LinkUp2026!')
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    target.password = hashed
    target.updated_at = datetime.utcnow()
    db.session.commit()
    return success_response("Password reset successfully")


@admin_bp.route('/api/admin/users/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_status(user, user_id):
    target = AdminUser.query.get(user_id)
    if not target:
        return error_response("Member not found", status_code=404)
    target.status = '0' if target.status == '1' else '1'
    target.updated_at = datetime.utcnow()
    db.session.commit()
    return success_response("Status updated", {'status': target.status})


@admin_bp.route('/api/admin/users/<int:user_id>/delete', methods=['POST', 'DELETE'])
@admin_required
def users_delete(user, user_id):
    target = AdminUser.query.get(user_id)
    if not target:
        return error_response("Member not found", status_code=404)
    target.deleted_at = datetime.utcnow()
    target.status = '0'
    db.session.commit()
    return success_response("Member deleted")


@admin_bp.route('/api/admin/users/<int:user_id>/wallet', methods=['GET'])
@admin_required
def users_wallet(user, user_id):
    wallet = UserWallet.query.filter_by(user_id=user_id).first()
    transactions = Transaction.query.filter_by(user_id=user_id)\
        .order_by(Transaction.created_at.desc()).limit(20).all()
    return success_response("Wallet loaded", {
        'wallet': wallet.to_dict() if wallet else None,
        'transactions': [t.to_dict() for t in transactions],
    })


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
