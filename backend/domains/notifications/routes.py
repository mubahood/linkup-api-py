"""
Notifications routes: /v1/notifications/*
"""
from flask import Blueprint, request
from backend.models import db
from backend.domains.notifications.models import Notification
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.utils.response import success_response, error_response, paginated_response
from backend.shared.utils.pagination import paginate_query

notifications_bp = Blueprint('v1_notifications', __name__, url_prefix='/v1/notifications')


@notifications_bp.route('', methods=['GET'])
@lu_jwt_required
def list_notifications(account):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    only_unread = request.args.get('unread', '').lower() == 'true'
    query = Notification.query.filter_by(account_id=account.id)
    if only_unread:
        query = query.filter_by(is_read=0)
    query = query.order_by(Notification.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([n.to_dict() for n in items], total, page, per_page, 'Notifications loaded.')


@notifications_bp.route('/unread-count', methods=['GET'])
@lu_jwt_required
def unread_count(account):
    """Lightweight badge count — returns just the number."""
    count = Notification.query.filter_by(account_id=account.id, is_read=0).count()
    return success_response('Unread count loaded.', {'unread_count': count})


@notifications_bp.route('/<notif_id>/read', methods=['POST'])
@lu_jwt_required
def mark_one_read(account, notif_id):
    """Mark a single notification as read."""
    notif = Notification.query.filter_by(id=notif_id, account_id=account.id).first()
    if not notif:
        return error_response('Notification not found.', status_code=404)
    notif.is_read = 1
    db.session.commit()
    return success_response('Notification read.', notif.to_dict())


@notifications_bp.route('/read', methods=['POST'])
@lu_jwt_required
def mark_read(account):
    data = request.get_json(silent=True) or {}
    ids = data.get('ids', [])
    if not ids:
        return error_response('ids array is required.')
    Notification.query.filter(
        Notification.id.in_(ids),
        Notification.account_id == account.id,
    ).update({'is_read': 1}, synchronize_session=False)
    db.session.commit()
    return success_response('Notifications marked as read.')


@notifications_bp.route('/read-all', methods=['POST'])
@lu_jwt_required
def mark_all_read(account):
    Notification.query.filter_by(account_id=account.id, is_read=0).update(
        {'is_read': 1}, synchronize_session=False
    )
    db.session.commit()
    return success_response('All notifications marked as read.')
