"""
Realtime chat + presence socket handlers (T-API-046/047/048).

Runs on the same Flask-SocketIO server as the calling stack, using a distinct
`chat:` event prefix so it never collides with call signalling. Delivery uses
Socket.IO rooms (auto-cleaned on disconnect):

  inbound  : chat:authenticate, chat:join_thread, chat:leave_thread, chat:typing
  outbound : chat:authenticated, chat:auth_error, message.new, message.read,
             typing.update, notification.new, presence.update

The REST layer pushes message.new / message.read / notification.new via
`backend/sockets/realtime.py`; this module only handles inbound socket events.
"""
from flask import request
from flask_socketio import join_room, leave_room, emit

from backend.models import db

# account_id -> set of socket sids (best-effort presence hint)
online_accounts: dict[str, set] = {}


def _account_from_token(token: str):
    from flask_jwt_extended import decode_token
    from backend.domains.identity.models import Account
    try:
        decoded = decode_token(token)
        return db.session.get(Account, str(decoded['sub']))
    except Exception:
        return None


def _is_participant(thread_id: str, account_id: str) -> bool:
    from backend.domains.chat.models import ThreadParticipant
    return ThreadParticipant.query.filter_by(
        thread_id=thread_id, account_id=account_id
    ).first() is not None


def register_chat_events(socketio, app):

    @socketio.on('chat:authenticate')
    def chat_authenticate(data):
        token = (data or {}).get('token', '')
        with app.app_context():
            acct = _account_from_token(token)
            if not acct:
                emit('chat:auth_error', {'error': 'Invalid or missing token'})
                return
            sid = request.sid
            join_room(f'user:{acct.id}')          # personal channel
            online_accounts.setdefault(acct.id, set()).add(sid)
            emit('chat:authenticated', {'account_id': acct.id})

    @socketio.on('chat:join_thread')
    def chat_join_thread(data):
        data = data or {}
        token = data.get('token', '')
        thread_id = data.get('thread_id')
        if not thread_id:
            return
        with app.app_context():
            acct = _account_from_token(token)
            if not acct or not _is_participant(thread_id, acct.id):
                emit('chat:auth_error', {'error': 'Not a participant of this thread'})
                return
            join_room(f'thread:{thread_id}')
            emit('chat:joined_thread', {'thread_id': thread_id})

    @socketio.on('chat:leave_thread')
    def chat_leave_thread(data):
        thread_id = (data or {}).get('thread_id')
        if thread_id:
            leave_room(f'thread:{thread_id}')

    @socketio.on('chat:typing')
    def chat_typing(data):
        """Relay an ephemeral typing indicator to the rest of the thread room."""
        data = data or {}
        token = data.get('token', '')
        thread_id = data.get('thread_id')
        is_typing = bool(data.get('is_typing', True))
        if not thread_id:
            return
        with app.app_context():
            acct = _account_from_token(token)
            if not acct or not _is_participant(thread_id, acct.id):
                return
            # Send to everyone in the thread except the sender.
            emit('typing.update',
                 {'thread_id': thread_id, 'account_id': acct.id, 'is_typing': is_typing},
                 room=f'thread:{thread_id}', include_self=False)
