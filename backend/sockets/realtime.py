"""
Realtime emit helpers (T-API-046/047/048).

Thin, side-effect-free wrappers the REST layer calls after it has persisted a
change, so connected clients receive a live push without polling. All sends are
best-effort: a socket failure must never break the originating HTTP request.

Channels (Socket.IO rooms):
  • `thread:<thread_id>` — everyone currently viewing a conversation
  • `user:<account_id>`  — a member's personal channel (notifications, presence)
"""
from __future__ import annotations


def _sio():
    # Lazy import to avoid a circular import at module load (app imports routes).
    from backend.app import socketio
    return socketio


def _safe_emit(event, payload, room):
    try:
        _sio().emit(event, payload, room=room)
    except Exception:
        pass


# ── Chat ────────────────────────────────────────────────────────────────────

def emit_message_new(thread_id: str, message: dict):
    """A new message was persisted — push it to everyone in the thread room."""
    _safe_emit('message.new', message, room=f'thread:{thread_id}')


def emit_message_read(thread_id: str, account_id: str, last_read_at: str | None):
    """A participant marked the thread read — update read receipts live."""
    _safe_emit('message.read',
               {'thread_id': thread_id, 'account_id': account_id, 'last_read_at': last_read_at},
               room=f'thread:{thread_id}')


# ── Notifications ───────────────────────────────────────────────────────────

def emit_notification(account_id: str, notification: dict):
    """Push a new in-app notification to the recipient's personal channel."""
    _safe_emit('notification.new', notification, room=f'user:{account_id}')
