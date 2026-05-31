"""
Chat routes: /v1/threads/*
"""
import uuid
from datetime import datetime
from flask import Blueprint, request
from backend.models import db
from backend.domains.chat.models import Thread, ThreadParticipant, Message
from backend.domains.chat.service import get_or_create_direct_thread, send_message, get_unread_count
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.utils.response import success_response, error_response, paginated_response
from backend.shared.utils.pagination import paginate_query

chat_v1_bp = Blueprint('v1_chat', __name__, url_prefix='/v1/threads')


@chat_v1_bp.route('', methods=['GET'])
@lu_jwt_required
def list_threads(account):
    """List threads with last message and unread count."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    my_thread_ids_list = [r[0] for r in db.session.query(ThreadParticipant.thread_id).filter_by(account_id=account.id).all()]
    if not my_thread_ids_list:
        return paginated_response([], 0, page, per_page, 'Threads loaded.')
    from sqlalchemy import case
    query = Thread.query.filter(Thread.id.in_(my_thread_ids_list)).order_by(
        Thread.last_message_at.desc(), Thread.created_at.desc()
    )
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)

    result = []
    for thread in items:
        last_msg = Message.query.filter_by(thread_id=thread.id).filter(
            Message.deleted_at.is_(None)
        ).order_by(Message.created_at.desc()).first()
        unread = get_unread_count(thread.id, account.id)
        participants = ThreadParticipant.query.filter_by(thread_id=thread.id).all()
        data = thread.to_dict(account.id, last_msg.to_dict() if last_msg else None, unread)
        data['participants'] = [p.to_dict() for p in participants]
        result.append(data)

    return paginated_response(result, total, page, per_page, 'Threads loaded.')


@chat_v1_bp.route('', methods=['POST'])
@lu_jwt_required
def create_thread(account):
    """Create a direct thread with another account."""
    data = request.get_json(silent=True) or {}
    participant_id = (data.get('participant_id') or '').strip()
    mode = data.get('mode', 'professional')
    if not participant_id:
        return error_response('participant_id is required.')
    if participant_id == account.id:
        return error_response('You cannot start a thread with yourself.')

    thread = get_or_create_direct_thread(account.id, participant_id, mode)
    participants = ThreadParticipant.query.filter_by(thread_id=thread.id).all()
    data_out = thread.to_dict(account.id)
    data_out['participants'] = [p.to_dict() for p in participants]
    return success_response('Thread created.', data_out, status_code=201)


@chat_v1_bp.route('/<thread_id>', methods=['GET'])
@lu_jwt_required
def get_thread(account, thread_id):
    participant = ThreadParticipant.query.filter_by(thread_id=thread_id, account_id=account.id).first()
    if not participant:
        return error_response('Thread not found.', status_code=404)
    thread = db.session.get(Thread, thread_id)
    participants = ThreadParticipant.query.filter_by(thread_id=thread_id).all()
    data = thread.to_dict(account.id)
    data['participants'] = [p.to_dict() for p in participants]
    return success_response('Thread loaded.', data)


@chat_v1_bp.route('/<thread_id>/messages', methods=['GET'])
@lu_jwt_required
def thread_messages(account, thread_id):
    participant = ThreadParticipant.query.filter_by(thread_id=thread_id, account_id=account.id).first()
    if not participant:
        return error_response('Thread not found.', status_code=404)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    query = Message.query.filter_by(thread_id=thread_id).filter(
        Message.deleted_at.is_(None)
    ).order_by(Message.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([m.to_dict() for m in items], total, page, per_page, 'Messages loaded.')


@chat_v1_bp.route('/<thread_id>/messages', methods=['POST'])
@lu_jwt_required
def post_message(account, thread_id):
    participant = ThreadParticipant.query.filter_by(thread_id=thread_id, account_id=account.id).first()
    if not participant:
        return error_response('Thread not found.', status_code=404)
    data = request.get_json(silent=True) or {}
    body = (data.get('body') or '').strip()
    msg_type = data.get('type', 'text')
    if not body:
        return error_response('Message body is required.')
    msg = send_message(thread_id, account.id, body, msg_type)
    return success_response('Message sent.', msg.to_dict(), status_code=201)


@chat_v1_bp.route('/<thread_id>/read', methods=['POST'])
@lu_jwt_required
def mark_read(account, thread_id):
    participant = ThreadParticipant.query.filter_by(thread_id=thread_id, account_id=account.id).first()
    if not participant:
        return error_response('Thread not found.', status_code=404)
    participant.last_read_at = datetime.utcnow()
    db.session.commit()
    return success_response('Marked as read.')
