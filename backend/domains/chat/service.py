"""
Chat service: thread creation, message sending.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import or_
from backend.models import db
from backend.domains.chat.models import Thread, ThreadParticipant, Message


def get_or_create_direct_thread(account_id: str, participant_id: str, mode: str = 'professional') -> Thread:
    """Get or create a direct thread between two accounts."""
    # Look for existing direct thread with both participants (MySQL-compatible, no INTERSECT)
    a_ids = [r[0] for r in db.session.query(ThreadParticipant.thread_id).filter_by(account_id=account_id).all()]
    b_ids = [r[0] for r in db.session.query(ThreadParticipant.thread_id).filter_by(account_id=participant_id).all()]
    shared_ids = list(set(a_ids) & set(b_ids))

    existing = None
    if shared_ids:
        existing = Thread.query.filter(
            Thread.id.in_(shared_ids),
            Thread.type == 'direct',
            Thread.mode == mode,
        ).first()

    if existing:
        return existing

    thread = Thread(
        id=str(uuid.uuid4()),
        type='direct',
        mode=mode,
        created_by=account_id,
    )
    db.session.add(thread)
    db.session.flush()

    for aid in [account_id, participant_id]:
        p = ThreadParticipant(
            id=str(uuid.uuid4()),
            thread_id=thread.id,
            account_id=aid,
        )
        db.session.add(p)

    db.session.commit()
    return thread


def send_message(thread_id: str, sender_id: str, body: str,
                 msg_type: str = 'text', media: list | None = None) -> Message:
    """Send a message and update thread's last_message_at."""
    msg = Message(
        id=str(uuid.uuid4()),
        thread_id=thread_id,
        sender_id=sender_id,
        body=body,
        type=msg_type,
        media=media,
    )
    db.session.add(msg)

    thread = db.session.get(Thread, thread_id)
    if thread:
        thread.last_message_at = datetime.utcnow()

    db.session.commit()
    return msg


def get_unread_count(thread_id: str, account_id: str) -> int:
    """Count unread messages in a thread for a given account."""
    participant = ThreadParticipant.query.filter_by(
        thread_id=thread_id, account_id=account_id
    ).first()
    if not participant:
        return 0
    last_read = participant.last_read_at
    query = Message.query.filter_by(thread_id=thread_id).filter(
        Message.deleted_at.is_(None),
        Message.sender_id != account_id,
    )
    if last_read:
        query = query.filter(Message.created_at > last_read)
    return query.count()


def has_unread_messages(account_id: str) -> bool:
    """Does this account have any unread message anywhere, across every
    thread? Reuses get_unread_count per thread (no separate query logic to
    drift out of sync with it) but short-circuits on the first hit instead
    of summing every thread the way GET /v1/threads does for its per-row
    badges — cheaper when the caller only needs a yes/no (the mobile home
    badge, and the daily local-notification content check)."""
    thread_ids = [
        r[0] for r in db.session.query(ThreadParticipant.thread_id)
        .filter_by(account_id=account_id).all()
    ]
    return any(get_unread_count(tid, account_id) > 0 for tid in thread_ids)
