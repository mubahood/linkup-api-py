"""Search service: MySQL LIKE-based search for Phase 0. Blocked accounts filtered."""
from sqlalchemy import or_
from backend.domains.identity.models import Account
from backend.domains.profile.models import ProfessionalProfile
from backend.domains.hubs.models import Hub
from backend.domains.jobs.models import Job


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
) -> list:
    """Search members by name or handle. Filtered by bio/headline for richer matches."""
    blocked = _get_blocked_ids(account_id)

    # Join with ProfessionalProfile to search bio + headline
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
            ),
        )
    )
    if blocked:
        base = base.filter(~Account.id.in_(blocked))
    if account_id:
        base = base.filter(Account.id != account_id)

    accounts = base.offset(offset).limit(limit).all()
    return [a.to_dict() for a in accounts]


def search_hubs(query: str, limit: int = 20, offset: int = 0) -> list:
    q = Hub.query.filter(
        Hub.is_public == 1,
        or_(Hub.name.ilike(f'%{query}%'), Hub.description.ilike(f'%{query}%')),
    ).offset(offset).limit(limit).all()
    return [h.to_dict() for h in q]


def search_jobs(query: str, limit: int = 20, offset: int = 0) -> list:
    q = Job.query.filter(
        Job.is_open == 1,
        or_(Job.title.ilike(f'%{query}%'), Job.description.ilike(f'%{query}%')),
    ).offset(offset).limit(limit).all()
    return [j.to_dict() for j in q]
