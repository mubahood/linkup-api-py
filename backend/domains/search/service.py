"""Search service: MySQL LIKE-based search for Phase 0."""
from backend.domains.identity.models import Account
from backend.domains.profile.models import ProfessionalProfile
from backend.domains.hubs.models import Hub
from backend.domains.jobs.models import Job


def search_people(query: str, dimension: str = '', limit: int = 20, offset: int = 0) -> list:
    q = Account.query.filter(
        Account.deleted_at.is_(None),
        Account.account_status == 'active',
        (Account.display_name.ilike(f'%{query}%') | Account.handle.ilike(f'%{query}%'))
    ).offset(offset).limit(limit).all()
    return [a.to_dict() for a in q]


def search_hubs(query: str, limit: int = 20, offset: int = 0) -> list:
    q = Hub.query.filter(
        Hub.is_public == 1,
        Hub.name.ilike(f'%{query}%'),
    ).offset(offset).limit(limit).all()
    return [h.to_dict() for h in q]


def search_jobs(query: str, limit: int = 20, offset: int = 0) -> list:
    q = Job.query.filter(
        Job.is_open == 1,
        Job.title.ilike(f'%{query}%'),
    ).offset(offset).limit(limit).all()
    return [j.to_dict() for j in q]
