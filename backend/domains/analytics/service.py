"""
Engagement analytics: aggregations over the existing BehavioralEvent log and
Account.last_seen_at, plus the trending-profiles scoring engine. No new
tables — this reads what sparks/routes.py, links/routes.py, jobs/routes.py,
posts/routes.py and hubs/routes.py already write via shared.events.emit().

No scheduler exists in this codebase (see subscriptions/service.py's own
lazy-expiry docstring) — every number here is computed lazily on read, same
convention, not on a timer.
"""
from __future__ import annotations
import random
from datetime import datetime, timedelta
from sqlalchemy import func
from backend.models import db
from backend.shared.events.models import BehavioralEvent
from backend.domains.identity.models import Account

# Weighted, rolling-window "how much attention has this profile gotten
# lately" score. Deliberately never returned to end users as a raw number —
# see sample_trending() — only used internally and by admin.
TRENDING_WEIGHTS = {
    'profile.view': 1,
    'spark.spark_up': 3,
    'spark.standout': 5,
}
TRENDING_WINDOW_DAYS = 7


def get_trending_account_ids(app_id: str, limit: int = 30) -> list[tuple[str, int]]:
    """[(account_id, score), ...] ordered by score desc — real numbers, for
    admin/internal use. End-user-facing code must go through
    sample_trending() instead of exposing this directly."""
    since = datetime.utcnow() - timedelta(days=TRENDING_WINDOW_DAYS)
    rows = (
        db.session.query(BehavioralEvent.object_id, BehavioralEvent.verb, func.count(BehavioralEvent.id))
        .join(Account, Account.id == BehavioralEvent.object_id)
        .filter(
            BehavioralEvent.object_type == 'account',
            BehavioralEvent.verb.in_(list(TRENDING_WEIGHTS.keys())),
            BehavioralEvent.created_at >= since,
            Account.app_id == app_id,
            Account.deleted_at.is_(None),
        )
        .group_by(BehavioralEvent.object_id, BehavioralEvent.verb)
        .all()
    )
    scores: dict = {}
    for object_id, verb, count in rows:
        scores[object_id] = scores.get(object_id, 0) + count * TRENDING_WEIGHTS[verb]
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    return ranked[:limit]


def sample_trending(candidate_ids: list, k: int = 10) -> list:
    """Randomly sample k ids from a trending pool — never a fixed
    deterministic top-N, so exact rank can't be inferred or farmed across
    repeated calls (same anti-gaming principle as the deck-jitter in
    sparks/service.py's get_deck())."""
    if len(candidate_ids) <= k:
        return list(candidate_ids)
    return random.sample(candidate_ids, k)


def get_engagement_overview(app_id: str) -> dict:
    """DAU/WAU/MAU from last_seen_at bucket counts, plus 7-day event volume
    by verb — powers the admin AnalyticsPage overview."""
    now = datetime.utcnow()

    def _active_since(days):
        return Account.query.filter(
            Account.app_id == app_id,
            Account.deleted_at.is_(None),
            Account.last_seen_at.isnot(None),
            Account.last_seen_at >= now - timedelta(days=days),
        ).count()

    since_7d = now - timedelta(days=7)
    verb_rows = (
        db.session.query(BehavioralEvent.verb, func.count(BehavioralEvent.id))
        .join(Account, Account.id == BehavioralEvent.account_id)
        .filter(Account.app_id == app_id, BehavioralEvent.created_at >= since_7d)
        .group_by(BehavioralEvent.verb)
        .order_by(func.count(BehavioralEvent.id).desc())
        .all()
    )
    return {
        'dau': _active_since(1),
        'wau': _active_since(7),
        'mau': _active_since(30),
        'events_by_verb_7d': [{'verb': v, 'count': c} for v, c in verb_rows],
    }


def get_contact_reveal_audit(app_id: str, page: int = 1, per_page: int = 20):
    """Who revealed whose contact, when — from the contact.reveal events
    sparks/routes.py:match_contact emits. Returns
    (rows, total, page, last_page, per_page) matching paginate_query's shape."""
    from backend.shared.utils.pagination import paginate_query
    query = (
        db.session.query(BehavioralEvent)
        .join(Account, Account.id == BehavioralEvent.account_id)
        .filter(Account.app_id == app_id, BehavioralEvent.verb == 'contact.reveal')
        .order_by(BehavioralEvent.created_at.desc())
    )
    items, total, p, last_page, pp = paginate_query(query, page, per_page)
    account_ids = {e.account_id for e in items} | {e.object_id for e in items}
    accounts = {a.id: a for a in Account.query.filter(Account.id.in_(account_ids)).all()}
    rows = []
    for e in items:
        actor = accounts.get(e.account_id)
        target = accounts.get(e.object_id)
        rows.append({
            'id': e.id,
            'actor_id': e.account_id,
            'actor_name': actor.display_name if actor else None,
            'target_id': e.object_id,
            'target_name': target.display_name if target else None,
            'match_id': (e.context or {}).get('match_id'),
            'created_at': e.created_at.isoformat() if e.created_at else None,
        })
    return rows, total, p, last_page, pp


def get_account_engagement(account_id: str) -> dict:
    """Per-account engagement snapshot — presence, location freshness, and
    30-day event counts given/received — for the admin AccountDetailDrawer's
    Engagement section. Returns {} for an unknown account_id."""
    account = db.session.get(Account, account_id)
    if not account:
        return {}
    since_30d = datetime.utcnow() - timedelta(days=30)
    given = (
        db.session.query(BehavioralEvent.verb, func.count(BehavioralEvent.id))
        .filter(BehavioralEvent.account_id == account_id, BehavioralEvent.created_at >= since_30d)
        .group_by(BehavioralEvent.verb)
        .all()
    )
    received = (
        db.session.query(BehavioralEvent.verb, func.count(BehavioralEvent.id))
        .filter(
            BehavioralEvent.object_id == account_id, BehavioralEvent.object_type == 'account',
            BehavioralEvent.created_at >= since_30d,
        )
        .group_by(BehavioralEvent.verb)
        .all()
    )
    return {
        'last_seen_at': account.last_seen_at.isoformat() if account.last_seen_at else None,
        'is_online': account.is_online(),
        'location_updated_at': account.location_updated_at.isoformat() if account.location_updated_at else None,
        'needs_location_update': account.needs_location_update(),
        'actions_given_30d': [{'verb': v, 'count': c} for v, c in given],
        'actions_received_30d': [{'verb': v, 'count': c} for v, c in received],
    }
