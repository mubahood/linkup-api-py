"""
Feed routes: /v1/feed/*

Home feed aggregates content from:
  1. Hub posts from hubs the user is a member of
  2. Recent job postings from connections' organisations
  3. Upcoming events the user or their connections care about
  4. Professional updates from direct Links

Feed items are ordered by recency (simple Phase 0 algorithm).
Phase 2: replace with ML-ranked candidate generation.
"""
from flask import Blueprint, request
from sqlalchemy import or_
from backend.models import db
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.utils.response import success_response
from backend.shared.utils.pagination import paginate_query
from backend.shared.utils.response import paginated_response

feed_bp = Blueprint('v1_feed', __name__, url_prefix='/v1/feed')


def _build_feed_item(item_type: str, data: dict, timestamp: str) -> dict:
    return {
        'type': item_type,
        'timestamp': timestamp,
        'data': data,
    }


@feed_bp.route('/home', methods=['GET'])
@lu_jwt_required
def home_feed(account):
    """
    Home feed for professional mode.
    Returns a mixed chronological stream of:
    - hub_post: posts from hubs the user belongs to
    - job_post: recent open jobs
    - event: upcoming events

    Paginated by cursor (page + per_page).
    """
    from backend.domains.hubs.models import Hub, HubMembership, HubPost, HubPostComment, HubPostLike
    from backend.domains.jobs.models import Job
    from backend.domains.events.models import Event, EventRSVP
    from backend.domains.links.models import Link
    from datetime import datetime, timedelta

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 50)
    feed_type = request.args.get('type', 'all')  # all | hub_posts | jobs | events

    items = []

    # ── Hub posts from joined hubs ────────────────────────────────────────
    if feed_type in ('all', 'hub_posts'):
        my_hub_ids = [r[0] for r in db.session.query(HubMembership.hub_id).filter_by(
            account_id=account.id
        ).all()]
        if my_hub_ids:
            hub_posts = HubPost.query.filter(
                HubPost.hub_id.in_(my_hub_ids),
                HubPost.deleted_at.is_(None),
            ).order_by(HubPost.created_at.desc()).limit(per_page * 3).all()

            for post in hub_posts:
                # Check if current user liked the post
                my_like = HubPostLike.query.filter_by(
                    post_id=post.id, account_id=account.id
                ).first()
                post_data = post.to_dict(my_like=bool(my_like))
                # Add hub info
                hub = db.session.get(Hub, post.hub_id)
                post_data['hub'] = {'id': hub.id, 'name': hub.name, 'slug': hub.slug} if hub else None
                items.append(_build_feed_item(
                    'hub_post',
                    post_data,
                    post.created_at.isoformat() if post.created_at else '',
                ))

    # ── Recent open jobs ──────────────────────────────────────────────────
    if feed_type in ('all', 'jobs'):
        jobs = Job.query.filter_by(is_open=1).order_by(
            Job.created_at.desc()
        ).limit(per_page).all()
        for job in jobs:
            items.append(_build_feed_item(
                'job_post',
                {'id': job.id, 'title': job.title, 'org_name': job.org_name,
                 'seniority': job.seniority, 'employment_type': job.employment_type,
                 'location_text': job.location_text, 'referral_open': bool(job.referral_open),
                 'created_at': job.created_at.isoformat() if job.created_at else ''},
                job.created_at.isoformat() if job.created_at else '',
            ))

    # ── Upcoming events ───────────────────────────────────────────────────
    if feed_type in ('all', 'events'):
        events = Event.query.filter(
            Event.start_at >= datetime.utcnow(),
            Event.start_at <= datetime.utcnow() + timedelta(days=30),
        ).order_by(Event.start_at.asc()).limit(per_page).all()
        for event in events:
            my_rsvp = EventRSVP.query.filter_by(event_id=event.id, account_id=account.id).first()
            items.append(_build_feed_item(
                'event',
                {'id': event.id, 'title': event.title, 'event_type': event.event_type,
                 'start_at': event.start_at.isoformat() if event.start_at else '',
                 'location_text': event.location_text, 'is_online': bool(event.is_online),
                 'my_rsvp': my_rsvp.status if my_rsvp else None},
                event.start_at.isoformat() if event.start_at else '',
            ))

    # Sort all items by timestamp descending (most recent first)
    items.sort(key=lambda x: x['timestamp'], reverse=True)

    # Manual pagination on the combined list
    total = len(items)
    start = (page - 1) * per_page
    page_items = items[start:start + per_page]
    last_page = max(1, (total + per_page - 1) // per_page)

    return success_response('Feed loaded.', {
        'current_page': page,
        'per_page': per_page,
        'total': total,
        'last_page': last_page,
        'data': page_items,
    })
