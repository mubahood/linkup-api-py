"""
Chat routes: /v1/threads/*
"""
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, request
from backend.models import db
from backend.domains.chat.models import Thread, ThreadParticipant, Message, MessageReaction
from backend.domains.chat.service import get_or_create_direct_thread, send_message, get_unread_count
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.idempotency import idempotent
from backend.shared.ratelimit import rate_limit
from backend.shared.utils.response import success_response, error_response, paginated_response
from backend.shared.utils.pagination import paginate_query


def _fmt_time(dt: datetime) -> str:
    """Human-friendly relative time label for conversation list."""
    if not dt:
        return ''
    now = datetime.utcnow()
    delta = now - dt
    secs = delta.total_seconds()
    if secs < 60:         return 'now'
    if secs < 3600:       return f'{int(secs / 60)}m'
    if secs < 86400:      return f'{int(secs / 3600)}h'
    if delta.days == 1:   return 'Yesterday'
    if delta.days < 7:    return dt.strftime('%a')
    return dt.strftime('%d %b')

chat_v1_bp = Blueprint('v1_chat', __name__, url_prefix='/v1/threads')


@chat_v1_bp.route('', methods=['GET'])
@lu_jwt_required
def list_threads(account):
    """
    List threads with last message and unread count.
    ?unread=true — only threads with unread messages
    ?archived=true — include archived threads (default: excluded)
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    only_unread = request.args.get('unread', '').lower() == 'true'
    include_archived = request.args.get('archived', '').lower() == 'true'

    ptq = db.session.query(ThreadParticipant.thread_id).filter_by(account_id=account.id)
    if not include_archived:
        ptq = ptq.filter(ThreadParticipant.is_archived == 0)
    my_thread_ids_list = [r[0] for r in ptq.all()]

    if not my_thread_ids_list:
        from backend.shared.utils.response import EMPTY_STATES
        return paginated_response([], 0, page, per_page, 'Threads loaded.',
                                  empty_state=EMPTY_STATES['threads'])
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
        if only_unread and unread == 0:
            continue
        participants = ThreadParticipant.query.filter_by(thread_id=thread.id).all()
        data = thread.to_dict(account.id, last_msg.to_dict(account.id) if last_msg else None, unread)
        data['participants'] = [p.to_dict() for p in participants]

        # ── Enrich with display name, avatar and last-message preview ───────
        other_parts = [p for p in participants if p.account_id != account.id]
        other = other_parts[0] if other_parts else None
        other_acct = other.account if other else None
        data['display_name'] = (
            other_acct.display_name if other_acct
            else thread.title or 'Chat'
        )
        data['avatar'] = other_acct.avatar if other_acct else None
        data['other_participant'] = other_acct.to_dict() if other_acct else None
        data['last_message_body'] = (last_msg.body or '') if last_msg else ''
        data['last_message_at_fmt'] = _fmt_time(thread.last_message_at)
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
    # ASC so oldest appears first; Flutter scrolls to bottom for newest
    # Respect per-participant clear: hide messages predating cleared_at
    msg_query = Message.query.filter_by(thread_id=thread_id).filter(
        Message.deleted_at.is_(None)
    )
    if participant and participant.cleared_at:
        msg_query = msg_query.filter(Message.created_at >= participant.cleared_at)
    query = msg_query.order_by(Message.created_at.asc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)

    # Resolve the other participant's last_read_at BEFORE marking myself as read,
    # so that read-receipts on my OWN messages are based on when THEY last read.
    all_parts = ThreadParticipant.query.filter_by(thread_id=thread_id).all()
    other_part = next((p for p in all_parts if p.account_id != account.id), None)
    recipient_read_at = other_part.last_read_at if other_part else None

    # Mark my participant as read now that I have fetched the messages
    if participant:
        participant.last_read_at = datetime.utcnow()
        try:
            db.session.commit()
            # Live read-receipt to the other side (T-API-047)
            from backend.sockets.realtime import emit_message_read
            emit_message_read(thread_id, account.id, participant.last_read_at.isoformat())
        except Exception:
            db.session.rollback()

    return paginated_response(
        [m.to_dict(viewer_id=account.id, recipient_read_at=recipient_read_at)
         for m in items],
        total, page, per_page, 'Messages loaded.'
    )


@chat_v1_bp.route('/<thread_id>/messages', methods=['POST'])
@lu_jwt_required
@idempotent
@rate_limit(30, 10)  # 30 messages / 10s (T-API-071)
def post_message(account, thread_id):
    participant = ThreadParticipant.query.filter_by(thread_id=thread_id, account_id=account.id).first()
    if not participant:
        return error_response('Thread not found.', status_code=404)
    data = request.get_json(silent=True) or {}
    body = (data.get('body') or '').strip()
    media = data.get('media')  # list of {url, type} or None
    msg_type = data.get('type', 'text')
    if not body and not media:
        return error_response('Message body or media is required.')
    # Content moderation hook (T-API-072) — soft flag, does not block in dev.
    from backend.shared.moderation import screen_text
    mod = screen_text(body)

    msg = send_message(thread_id, account.id, body, msg_type, media=media)
    msg_dict = msg.to_dict(viewer_id=account.id)
    from backend.shared.events.emit import emit
    emit('message.send', account_id=account.id, object_type='thread', object_id=thread_id)
    if mod['flagged']:
        emit('moderation.flag', account_id=account.id, object_type='message',
             object_id=msg.id, context={'reason': mod['reason'], 'score': mod['score']})

    # Realtime push to everyone viewing the thread (T-API-046)
    try:
        from backend.sockets.realtime import emit_message_new
        emit_message_new(thread_id, msg_dict)
    except Exception:
        pass

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

    return success_response('Message sent.', msg_dict, status_code=201)


@chat_v1_bp.route('/<thread_id>/media', methods=['POST'])
@lu_jwt_required
def upload_chat_media(account, thread_id):
    """
    Upload a file (image or audio) for a chat message.
    Accepts multipart/form-data with field 'file'.
    Returns { url, type, filename } — caller then POSTs a message with the url.
    """
    participant = ThreadParticipant.query.filter_by(
        thread_id=thread_id, account_id=account.id).first()
    if not participant:
        return error_response('Thread not found.', status_code=404)

    from flask import request as _req
    if 'file' not in _req.files:
        return error_response('No file field in request.')

    file = _req.files['file']
    if not file or not file.filename:
        return error_response('Empty file.')

    from backend.shared.storage import save_upload
    from backend.shared.storage.local import (
        ALLOWED_IMAGE_EXTENSIONS, ALLOWED_AUDIO_EXTENSIONS,
    )

    url = save_upload(file, folder='chat_media')
    if not url:
        return error_response(
            'Upload failed — unsupported file type or server error.',
            status_code=422,
        )

    ext = (file.filename.rsplit('.', 1)[-1].lower()
           if '.' in file.filename else '')
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        media_type = 'image'
    elif ext in ALLOWED_AUDIO_EXTENSIONS:
        media_type = 'audio'
    else:
        media_type = 'file'

    return success_response('Media uploaded.', {
        'url': url,
        'type': media_type,
        'filename': file.filename,
    }, status_code=201)


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


@chat_v1_bp.route('/<thread_id>/participants', methods=['GET'])
@lu_jwt_required
def list_participants(account, thread_id):
    """List all participants in a thread with their account details and last-read time."""
    my_part = ThreadParticipant.query.filter_by(thread_id=thread_id, account_id=account.id).first()
    if not my_part:
        return error_response('Thread not found.', status_code=404)
    participants = ThreadParticipant.query.filter_by(thread_id=thread_id).all()
    return success_response('Participants loaded.', [p.to_dict() for p in participants])


@chat_v1_bp.route('/<thread_id>/archive', methods=['POST'])
@lu_jwt_required
def archive_thread(account, thread_id):
    """
    Archive a thread for this participant — hides it from the default thread list.
    The other participant's view is unaffected.
    POST /v1/threads/:id/archive — toggles archive state.
    """
    participant = ThreadParticipant.query.filter_by(thread_id=thread_id, account_id=account.id).first()
    if not participant:
        return error_response('Thread not found.', status_code=404)
    participant.is_archived = 0 if participant.is_archived else 1
    db.session.commit()
    state = 'archived' if participant.is_archived else 'unarchived'
    return success_response(f'Thread {state}.', {'is_archived': bool(participant.is_archived)})


@chat_v1_bp.route('/<thread_id>/clear', methods=['POST'])
@lu_jwt_required
def clear_thread(account, thread_id):
    """
    Clear this thread from the current participant's view.
    Sets cleared_at = now() so all existing messages are hidden for them only.
    The other participant's view is unaffected.
    """
    participant = ThreadParticipant.query.filter_by(thread_id=thread_id, account_id=account.id).first()
    if not participant:
        return error_response('Thread not found.', status_code=404)
    participant.cleared_at = datetime.utcnow()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return error_response('Failed to clear chat.', status_code=500)
    return success_response('Chat cleared.')


@chat_v1_bp.route('/<thread_id>/read', methods=['POST'])
@lu_jwt_required
def mark_read(account, thread_id):
    participant = ThreadParticipant.query.filter_by(thread_id=thread_id, account_id=account.id).first()
    if not participant:
        return error_response('Thread not found.', status_code=404)
    participant.last_read_at = datetime.utcnow()
    db.session.commit()
    return success_response('Marked as read.')
