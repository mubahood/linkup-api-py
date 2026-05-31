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


@events_bp.route('/mine', methods=['GET'])
@lu_jwt_required
def my_events(account):
    """Events I created (past + upcoming)."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = Event.query.filter_by(created_by=account.id).order_by(Event.start_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([_enrich_event(e, account.id) for e in items], total, page, per_page, 'My events loaded.')


@events_bp.route('/going', methods=['GET'])
@lu_jwt_required
def events_going(account):
    """Events I've RSVP'd 'going' to (upcoming only)."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = (
        Event.query
        .join(EventRSVP, EventRSVP.event_id == Event.id)
        .filter(
            EventRSVP.account_id == account.id,
            EventRSVP.status == 'going',
            Event.start_at >= datetime.utcnow(),
        )
        .order_by(Event.start_at.asc())
    )
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([_enrich_event(e, account.id) for e in items], total, page, per_page, 'Attending events loaded.')


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


@events_bp.route('/<event_id>', methods=['PUT'])
@lu_jwt_required
def update_event(account, event_id):
    """Update event — host only."""
    event = Event.query.get(event_id)
    if not event:
        return error_response('Event not found.', status_code=404)
    if event.created_by != account.id:
        return error_response('Only the event host can update this event.', status_code=403)
    data = request.get_json(silent=True) or {}
    for field in ['title', 'description', 'event_type', 'location_text', 'link', 'max_attendees']:
        if field in data:
            setattr(event, field, data[field])
    if 'is_online' in data:
        event.is_online = int(data['is_online'])
    if 'start_at' in data:
        try:
            event.start_at = datetime.fromisoformat(str(data['start_at']).replace('Z', '+00:00'))
        except Exception:
            return error_response('Invalid start_at format.')
    if 'end_at' in data:
        try:
            event.end_at = datetime.fromisoformat(str(data['end_at']).replace('Z', '+00:00'))
        except Exception:
            return error_response('Invalid end_at format.')
    db.session.commit()
    return success_response('Event updated.', _enrich_event(event, account.id))


@events_bp.route('/<event_id>', methods=['DELETE'])
@lu_jwt_required
def cancel_event(account, event_id):
    """Cancel / delete an event — host only."""
    event = Event.query.get(event_id)
    if not event:
        return error_response('Event not found.', status_code=404)
    if event.created_by != account.id:
        return error_response('Only the event host can cancel this event.', status_code=403)
    db.session.delete(event)
    db.session.commit()
    return success_response('Event cancelled.')


@events_bp.route('/<event_id>/attendees', methods=['GET'])
@lu_jwt_required
def attendees(account, event_id):
    """List attendees with going/maybe/not_going status."""
    event = Event.query.get(event_id)
    if not event:
        return error_response('Event not found.', status_code=404)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status_filter = request.args.get('status', '')  # going | maybe | not_going | all

    query = EventRSVP.query.filter_by(event_id=event_id)
    if status_filter and status_filter != 'all':
        query = query.filter(EventRSVP.status == status_filter)
    query = query.order_by(EventRSVP.created_at.asc())

    from backend.shared.utils.pagination import paginate_query
    from backend.shared.utils.response import paginated_response
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)

    result = []
    for rsvp in items:
        from backend.domains.identity.models import Account
        acc = db.session.get(Account, rsvp.account_id)
        entry = rsvp.to_dict()
        entry['account'] = acc.to_dict() if acc else None
        result.append(entry)

    return paginated_response(result, total, page, per_page, 'Attendees loaded.')


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
