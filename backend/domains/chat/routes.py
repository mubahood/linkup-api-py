"""
Chat routes: /v1/threads/*
"""
import uuid
from datetime import datetime
from flask import Blueprint, request
from backend.models import db
from backend.domains.chat.models import Thread, ThreadParticipant, Message, MessageReaction
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

    # Notify all other participants
    try:
        from backend.domains.notifications.service import create_notification
        other_participants = ThreadParticipant.query.filter(
            ThreadParticipant.thread_id == thread_id,
            ThreadParticipant.account_id != account.id,
        ).all()
        preview = body[:80] + ('…' if len(body) > 80 else '')
        for p in other_participants:
            create_notification(
                account_id=p.account_id,
                notif_type='message.sent',
                title=f'New message from {account.display_name}',
                body=preview,
                data={'thread_id': thread_id, 'sender_id': account.id},
                action_url=f'/chat/{thread_id}',
            )
    except Exception:
        pass

    return success_response('Message sent.', msg.to_dict(), status_code=201)


@chat_v1_bp.route('/<thread_id>/messages/<message_id>', methods=['DELETE'])
@lu_jwt_required
def delete_message(account, thread_id, message_id):
    """
    Delete / unsend a message.
    - Sender can delete within 24 hours (soft-delete: body replaced)
    - After 24h, returns 403 (message is part of conversation history)
    """
    participant = ThreadParticipant.query.filter_by(thread_id=thread_id, account_id=account.id).first()
    if not participant:
        return error_response('Thread not found.', status_code=404)
    msg = Message.query.filter_by(id=message_id, thread_id=thread_id).filter(
        Message.deleted_at.is_(None)
    ).first()
    if not msg:
        return error_response('Message not found.', status_code=404)
    if msg.sender_id != account.id:
        return error_response('You can only delete your own messages.', status_code=403)
    # Allow deletion within 24 hours
    from datetime import timedelta
    age = datetime.utcnow() - msg.created_at
    if age > timedelta(hours=24):
        return error_response('Messages can only be deleted within 24 hours of sending.', status_code=403)
    msg.deleted_at = datetime.utcnow()
    msg.body = '[Message deleted]'
    db.session.commit()
    return success_response('Message deleted.')


@chat_v1_bp.route('/<thread_id>/messages/<message_id>/react', methods=['POST'])
@lu_jwt_required
def react_message(account, thread_id, message_id):
    """Toggle an emoji reaction on a message."""
    participant = ThreadParticipant.query.filter_by(thread_id=thread_id, account_id=account.id).first()
    if not participant:
        return error_response('Thread not found.', status_code=404)

    msg = Message.query.filter_by(id=message_id, thread_id=thread_id).filter(
        Message.deleted_at.is_(None)
    ).first()
    if not msg:
        return error_response('Message not found.', status_code=404)

    data = request.get_json(silent=True) or {}
    emoji = (data.get('emoji') or '👍').strip()
    if len(emoji) > 10:
        return error_response('Emoji must be a single emoji character.')

    existing = MessageReaction.query.filter_by(
        message_id=message_id, account_id=account.id, emoji=emoji
    ).first()

    if existing:
        # Remove (toggle off)
        db.session.delete(existing)
        db.session.commit()
        return success_response('Reaction removed.', {'reacted': False, 'emoji': emoji})

    reaction = MessageReaction(
        id=str(uuid.uuid4()),
        message_id=message_id,
        account_id=account.id,
        emoji=emoji,
    )
    db.session.add(reaction)
    db.session.commit()
    return success_response('Reaction added.', reaction.to_dict(), status_code=201)


@chat_v1_bp.route('/<thread_id>/messages/<message_id>/reactions', methods=['GET'])
@lu_jwt_required
def message_reactions(account, thread_id, message_id):
    """List all reactions on a message, grouped by emoji."""
    participant = ThreadParticipant.query.filter_by(thread_id=thread_id, account_id=account.id).first()
    if not participant:
        return error_response('Thread not found.', status_code=404)

    msg = Message.query.filter_by(id=message_id, thread_id=thread_id).filter(
        Message.deleted_at.is_(None)
    ).first()
    if not msg:
        return error_response('Message not found.', status_code=404)

    reactions = MessageReaction.query.filter_by(message_id=message_id).all()

    # Group by emoji for a summary count
    grouped: dict = {}
    for r in reactions:
        if r.emoji not in grouped:
            grouped[r.emoji] = {'emoji': r.emoji, 'count': 0, 'reacted_by_me': False, 'accounts': []}
        grouped[r.emoji]['count'] += 1
        if r.account_id == account.id:
            grouped[r.emoji]['reacted_by_me'] = True
        if grouped[r.emoji]['count'] <= 5 and r.account:
            grouped[r.emoji]['accounts'].append(r.account.to_dict())

    return success_response('Reactions loaded.', {
        'message_id': message_id,
        'total': len(reactions),
        'summary': list(grouped.values()),
    })


@chat_v1_bp.route('/<thread_id>/read', methods=['POST'])
@lu_jwt_required
def mark_read(account, thread_id):
    participant = ThreadParticipant.query.filter_by(thread_id=thread_id, account_id=account.id).first()
    if not participant:
        return error_response('Thread not found.', status_code=404)
    participant.last_read_at = datetime.utcnow()
    db.session.commit()
    return success_response('Marked as read.')
