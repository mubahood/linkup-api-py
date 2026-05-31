"""
Events routes: /v1/events/*
"""
import uuid
from datetime import datetime
from flask import Blueprint, request
from backend.models import db
from backend.domains.events.models import Event, EventRSVP
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.utils.response import success_response, error_response, paginated_response
from backend.shared.utils.pagination import paginate_query

events_bp = Blueprint('v1_events', __name__, url_prefix='/v1/events')


def _enrich_event(event: Event, account_id: str) -> dict:
    rsvp = EventRSVP.query.filter_by(event_id=event.id, account_id=account_id).first()
    count = EventRSVP.query.filter_by(event_id=event.id, status='going').count()
    return event.to_dict(my_rsvp=rsvp, attendee_count=count)


@events_bp.route('', methods=['GET'])
@lu_jwt_required
def list_events(account):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    q = request.args.get('q', '')
    query = Event.query
    if q:
        query = query.filter(Event.title.ilike(f'%{q}%'))
    query = query.filter(Event.start_at >= datetime.utcnow()).order_by(Event.start_at.asc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([_enrich_event(e, account.id) for e in items], total, page, per_page, 'Events loaded.')


@events_bp.route('', methods=['POST'])
@lu_jwt_required
def create_event(account):
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    start_at = data.get('start_at')
    if not title:
        return error_response('Event title is required.')
    if not start_at:
        return error_response('start_at is required.')

    try:
        start_dt = datetime.fromisoformat(str(start_at).replace('Z', '+00:00'))
    except Exception:
        return error_response('Invalid start_at datetime format.')

    end_dt = None
    if data.get('end_at'):
        try:
            end_dt = datetime.fromisoformat(str(data['end_at']).replace('Z', '+00:00'))
        except Exception:
            pass

    event = Event(
        id=str(uuid.uuid4()),
        created_by=account.id,
        title=title,
        description=data.get('description'),
        event_type=data.get('event_type', 'networking'),
        start_at=start_dt,
        end_at=end_dt,
        location_text=data.get('location_text'),
        is_online=int(data.get('is_online', 0)),
        link=data.get('link'),
        org_id=data.get('org_id'),
        max_attendees=data.get('max_attendees'),
    )
    db.session.add(event)
    db.session.commit()
    return success_response('Event created.', _enrich_event(event, account.id), status_code=201)


@events_bp.route('/<event_id>', methods=['GET'])
@lu_jwt_required
def get_event(account, event_id):
    event = Event.query.get(event_id)
    if not event:
        return error_response('Event not found.', status_code=404)
    return success_response('Event loaded.', _enrich_event(event, account.id))


@events_bp.route('/<event_id>/rsvp', methods=['POST'])
@lu_jwt_required
def rsvp(account, event_id):
    event = Event.query.get(event_id)
    if not event:
        return error_response('Event not found.', status_code=404)
    data = request.get_json(silent=True) or {}
    status = data.get('status', 'going')
    if status not in ('going', 'maybe', 'not_going'):
        return error_response('Invalid status. Use: going, maybe, not_going.')
    existing = EventRSVP.query.filter_by(event_id=event_id, account_id=account.id).first()
    if existing:
        existing.status = status
    else:
        existing = EventRSVP(
            id=str(uuid.uuid4()),
            event_id=event_id,
            account_id=account.id,
            status=status,
        )
        db.session.add(existing)
    db.session.commit()
    return success_response('RSVP recorded.', existing.to_dict())
