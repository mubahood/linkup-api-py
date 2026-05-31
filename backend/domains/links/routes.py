"""
Links routes: /v1/links/*
"""
import uuid
from flask import Blueprint, request
from sqlalchemy import or_
from backend.models import db
from backend.domains.links.models import Link
from backend.domains.links.service import get_link_suggestions
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.utils.response import success_response, error_response, paginated_response
from backend.shared.utils.pagination import paginate_query

links_bp = Blueprint('v1_links', __name__, url_prefix='/v1/links')


@links_bp.route('', methods=['GET'])
@lu_jwt_required
def my_links(account):
    """Get my accepted connections."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = Link.query.filter(
        or_(Link.requester_id == account.id, Link.addressee_id == account.id),
        Link.status == 'accepted'
    ).order_by(Link.updated_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([l.to_dict(account.id) for l in items], total, page, per_page, 'Links loaded.')


@links_bp.route('/requests', methods=['GET'])
@lu_jwt_required
def link_requests(account):
    """Get pending requests (sent + received)."""
    sent = Link.query.filter_by(requester_id=account.id, status='requested').all()
    received = Link.query.filter_by(addressee_id=account.id, status='requested').all()
    return success_response('Link requests loaded.', {
        'sent': [l.to_dict(account.id) for l in sent],
        'received': [l.to_dict(account.id) for l in received],
    })


@links_bp.route('/request', methods=['POST'])
@lu_jwt_required
def send_request(account):
    """Send a link request."""
    data = request.get_json(silent=True) or {}
    target_id = data.get('target_id', '').strip()
    note = data.get('note', '')

    if not target_id:
        return error_response('target_id is required.')
    if target_id == account.id:
        return error_response('You cannot link with yourself.')

    existing = Link.query.filter(
        or_(
            (Link.requester_id == account.id) & (Link.addressee_id == target_id),
            (Link.requester_id == target_id) & (Link.addressee_id == account.id),
        )
    ).first()

    if existing:
        if existing.status == 'accepted':
            return error_response('You are already connected with this person.')
        if existing.status == 'requested':
            return error_response('A link request already exists.')
        if existing.status == 'declined':
            # Allow re-request
            existing.status = 'requested'
            existing.requester_id = account.id
            existing.addressee_id = target_id
            existing.note = note
            db.session.commit()
            return success_response('Link request sent.', existing.to_dict(account.id))

    link = Link(
        id=str(uuid.uuid4()),
        requester_id=account.id,
        addressee_id=target_id,
        note=note,
        status='requested',
    )
    db.session.add(link)
    db.session.commit()

    # Notify the target
    try:
        from backend.domains.notifications.service import create_notification
        create_notification(
            account_id=target_id,
            notif_type='link.requested',
            title=f'{account.display_name} wants to Link with you',
            body=note or 'You have a new Link request.',
            data={'link_id': link.id, 'requester_id': account.id},
            action_url=f'/links/requests',
        )
    except Exception:
        pass  # Notifications are non-critical

    return success_response('Link request sent.', link.to_dict(account.id), status_code=201)


@links_bp.route('/<link_id>/accept', methods=['POST'])
@lu_jwt_required
def accept_request(account, link_id):
    link = Link.query.filter_by(id=link_id, addressee_id=account.id, status='requested').first()
    if not link:
        return error_response('Link request not found.', status_code=404)
    link.status = 'accepted'
    db.session.commit()

    # Notify the requester that their request was accepted
    try:
        from backend.domains.notifications.service import create_notification
        create_notification(
            account_id=link.requester_id,
            notif_type='link.accepted',
            title=f'{account.display_name} accepted your Link request',
            body='You are now connected. Start a conversation!',
            data={'link_id': link.id, 'accepter_id': account.id},
            action_url=f'/profile/@{account.handle}',
        )
    except Exception:
        pass

    return success_response('Link request accepted.', link.to_dict(account.id))


@links_bp.route('/<link_id>/decline', methods=['POST'])
@lu_jwt_required
def decline_request(account, link_id):
    link = Link.query.filter_by(id=link_id, addressee_id=account.id, status='requested').first()
    if not link:
        return error_response('Link request not found.', status_code=404)
    link.status = 'declined'
    db.session.commit()
    return success_response('Link request declined.')


@links_bp.route('/<link_id>', methods=['GET'])
@lu_jwt_required
def link_detail(account, link_id):
    """Get a single link with both account profiles."""
    link = Link.query.filter(
        Link.id == link_id,
        or_(Link.requester_id == account.id, Link.addressee_id == account.id)
    ).first()
    if not link:
        return error_response('Link not found.', status_code=404)
    from backend.domains.identity.models import Account
    requester = db.session.get(Account, link.requester_id)
    addressee = db.session.get(Account, link.addressee_id)
    data = link.to_dict(account.id)
    data['requester'] = requester.to_dict() if requester else None
    data['addressee'] = addressee.to_dict() if addressee else None
    return success_response('Link loaded.', data)


@links_bp.route('/<link_id>', methods=['DELETE'])
@lu_jwt_required
def remove_link(account, link_id):
    link = Link.query.filter(
        Link.id == link_id,
        or_(Link.requester_id == account.id, Link.addressee_id == account.id)
    ).first()
    if not link:
        return error_response('Link not found.', status_code=404)
    db.session.delete(link)
    db.session.commit()
    return success_response('Link removed.')


@links_bp.route('/suggestions', methods=['GET'])
@lu_jwt_required
def suggestions(account):
    return success_response('Suggestions loaded.', get_link_suggestions(account.id))
