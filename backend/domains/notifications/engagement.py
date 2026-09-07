"""
Server-side ("online") re-engagement job — reaches genuinely inactive
accounts that the client's LocalEngagementService structurally can't: local
notifications only re-arm when the app is opened (see
lib/shared/services/local_engagement_service.dart), so a user who's actually
gone quiet never gets a fresh one scheduled. This runs independently of any
device being online, via OneSignal push — see run_engagement_job() below and
background_engagement_job.py at the repo root for the actual cron entry
point.

Priority per account (richest, most relevant signal first — mirrors the
client's own _buildDailyContentPool priority, computed server-side instead
of requiring a live app session):
  1. An unread message waiting — the sender's photo, since they're already
     in a mutual thread (same "already visible" reasoning create_notification
     itself documents for message.sent).
  2. A real discovery candidate near them — the full interest-graph deck
     (get_deck), not a shortcut; the same query the client's
     "notification-candidate" browse feature uses.
  3. A generic nudge, no image, if truly nothing else surfaced (e.g. a
     sparse area with no fresh candidates).
"""
from __future__ import annotations
import logging
import random
from datetime import datetime, timedelta
from backend.models import db

logger = logging.getLogger(__name__)

_NOTIF_TYPE = 'engagement.comeback'
# Sweet spot: long enough that a "come back" nudge isn't annoying someone
# who was just here yesterday, short enough that we're still reaching
# people while there's a real chance of winning them back rather than
# someone who's fully churned.
_MIN_INACTIVE_DAYS = 2
_MAX_INACTIVE_DAYS = 21
# Matches the client-side come-back sequence's spacing (3-day / 7-day) —
# never more than once every 3 days per account, regardless of how often
# the job itself runs.
_COOLDOWN_DAYS = 3


def _eligible_accounts():
    from backend.domains.identity.models import Account
    now = datetime.utcnow()
    window_start = now - timedelta(days=_MAX_INACTIVE_DAYS)
    window_end = now - timedelta(days=_MIN_INACTIVE_DAYS)
    return Account.query.filter(
        Account.deleted_at.is_(None),
        Account.account_status == 'active',
        Account.last_seen_at.isnot(None),
        Account.last_seen_at >= window_start,
        Account.last_seen_at <= window_end,
    ).all()


def _recently_notified(account_id: str) -> bool:
    from backend.domains.notifications.models import Notification
    cutoff = datetime.utcnow() - timedelta(days=_COOLDOWN_DAYS)
    return db.session.query(Notification.id).filter(
        Notification.account_id == account_id,
        Notification.type == _NOTIF_TYPE,
        Notification.created_at >= cutoff,
    ).first() is not None


def _unread_message_content(account_id: str):
    """Most recent unread message across every thread this account is in, if
    any — (title, body, image_url, action_url), or None."""
    from backend.domains.chat.models import ThreadParticipant, Message
    from backend.domains.chat.service import get_unread_count
    from backend.domains.notifications.service import photo_for_account

    my_thread_ids = [
        r[0] for r in db.session.query(ThreadParticipant.thread_id)
        .filter_by(account_id=account_id).all()
    ]
    if not my_thread_ids:
        return None

    msg = (Message.query.filter(
        Message.thread_id.in_(my_thread_ids),
        Message.sender_id != account_id,
        Message.deleted_at.is_(None),
    ).order_by(Message.created_at.desc()).first())
    if not msg or get_unread_count(msg.thread_id, account_id) <= 0:
        return None

    sender_name = msg.sender.display_name if msg.sender else 'Someone'
    preview = (msg.body or '').strip()[:80]
    return (
        f'{sender_name} sent you a message',
        preview or "You've got a message waiting.",
        photo_for_account(msg.sender_id),
        f'/chat/{msg.thread_id}',
    )


def _discovery_candidate_content(account_id: str):
    """A real card off the same interest-graph deck /sparks/deck uses —
    reused directly rather than a separate lookup, so this is exactly as
    relevant as what the person would actually see if they opened the app."""
    from backend.domains.sparks.service import get_deck
    cards = get_deck(account_id, limit=1)
    if not cards:
        return None
    card = cards[0]
    photos = card.get('photos') or []
    photo_url = photos[0]['url'] if photos and photos[0].get('url') else None
    name = (card.get('display_name') or '').split(' ')[0] or 'Someone new'
    dp = card.get('dating_profile') or {}
    loc = dp.get('location_label')
    handle = card.get('handle')
    body = f'{name} is nearby — {loc}' if loc else f'{name} is nearby. Take a look.'
    action_url = f'/profile/@{handle}' if handle else '/sparks'
    return (f'{name} is on the app right now', body, photo_url, action_url)


def _generic_content():
    pairs = [
        ("New people joined near you", "Come see who's new — open the app to browse."),
        ("Your next match could be one swipe away", "It's been a few days. Come take a look."),
        ("Still there?", "People near you are active right now. Don't miss out."),
    ]
    title, body = random.choice(pairs)
    return (title, body, None, '/sparks')


def build_engagement_content(account_id: str):
    return (
        _unread_message_content(account_id)
        or _discovery_candidate_content(account_id)
        or _generic_content()
    )


def run_engagement_job(limit: int | None = None) -> dict:
    """The actual scheduled job entry point — see background_engagement_job.py.
    Best-effort per account: one account's failure (a data quirk, a
    transient OneSignal error) must never stop the rest of the batch."""
    from backend.domains.notifications.service import create_notification

    accounts = _eligible_accounts()
    if limit:
        accounts = accounts[:limit]

    sent, skipped_cooldown, failed = 0, 0, 0
    for account in accounts:
        try:
            if _recently_notified(account.id):
                skipped_cooldown += 1
                continue
            title, body, image_url, action_url = build_engagement_content(account.id)
            create_notification(
                account_id=account.id,
                notif_type=_NOTIF_TYPE,
                title=title,
                body=body,
                image_url=image_url,
                action_url=action_url,
                data={'kind': 'engagement'},
            )
            sent += 1
        except Exception:
            logger.exception(f'[EngagementJob] Failed for account {account.id}')
            failed += 1

    result = {
        'eligible': len(accounts), 'sent': sent,
        'skipped_cooldown': skipped_cooldown, 'failed': failed,
    }
    logger.info(f'[EngagementJob] {result}')
    return result
