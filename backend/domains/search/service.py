"""Search service: MySQL LIKE-based search for Phase 0. Blocked accounts filtered."""
from sqlalchemy import or_, func
from backend.domains.identity.models import Account
from backend.domains.profile.models import ProfessionalProfile
from backend.domains.hubs.models import Hub
from backend.domains.jobs.models import Job
from backend.models import db


def _get_blocked_ids(account_id: str) -> set:
    """Get IDs of accounts blocked by or blocking this account."""
    if not account_id:
        return set()
    try:
        from backend.domains.safety.models import Block
        blocked = {b.blocked_id for b in Block.query.filter_by(blocker_id=account_id).all()}
        blockers = {b.blocker_id for b in Block.query.filter_by(blocked_id=account_id).all()}
        return blocked | blockers
    except Exception:
        return set()


def search_people(
    query: str,
    account_id: str = '',
    dimension: str = '',
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Search members by name, handle, headline, or bio. Returns {data, total}."""
    blocked = _get_blocked_ids(account_id)

    base = (
        Account.query
        .outerjoin(ProfessionalProfile, ProfessionalProfile.account_id == Account.id)
        .filter(
            Account.deleted_at.is_(None),
            Account.account_status == 'active',
            or_(
                Account.display_name.ilike(f'%{query}%'),
                Account.handle.ilike(f'%{query}%'),
                ProfessionalProfile.headline.ilike(f'%{query}%'),
                ProfessionalProfile.bio.ilike(f'%{query}%'),
            ),
        )
    )
    if blocked:
        base = base.filter(~Account.id.in_(blocked))
    if account_id:
        base = base.filter(Account.id != account_id)

    total = base.count()
    accounts = base.offset(offset).limit(limit).all()
    return {
        'data': [a.to_dict() for a in accounts],
        'total': total,
        'limit': limit,
        'offset': offset,
    }


def search_hubs(query: str, limit: int = 20, offset: int = 0) -> dict:
    base = Hub.query.filter(
        Hub.is_public == 1,
        or_(Hub.name.ilike(f'%{query}%'), Hub.description.ilike(f'%{query}%')),
    )
    total = base.count()
    hubs = base.offset(offset).limit(limit).all()
    return {
        'data': [h.to_dict() for h in hubs],
        'total': total,
        'limit': limit,
        'offset': offset,
    }


def search_jobs(query: str, limit: int = 20, offset: int = 0) -> dict:
    base = Job.query.filter(
        Job.is_open == 1,
        or_(Job.title.ilike(f'%{query}%'), Job.description.ilike(f'%{query}%'),
            Job.org_name.ilike(f'%{query}%')),
    )
    total = base.count()
    jobs = base.offset(offset).limit(limit).all()
    return {
        'data': [j.to_dict() for j in jobs],
        'total': total,
        'limit': limit,
        'offset': offset,
    }


def search_events(query: str, limit: int = 20, offset: int = 0) -> dict:
    """Search events by title, description, or location."""
    from backend.domains.events.models import Event
    base = Event.query.filter(
        or_(
            Event.title.ilike(f'%{query}%'),
            Event.description.ilike(f'%{query}%'),
            Event.location_text.ilike(f'%{query}%'),
        ),
    ).order_by(Event.start_at.asc())
    total = base.count()
    events = base.offset(offset).limit(limit).all()
    return {
        'data': [e.to_dict() for e in events],
        'total': total,
        'limit': limit,
        'offset': offset,
    }
