"""
Links service: suggestion logic.
"""
from sqlalchemy import or_
from backend.domains.links.models import Link
from backend.domains.identity.models import Account
from backend.domains.interest.models import InterestProfile


def get_link_suggestions(account_id: str, limit: int = 10) -> list:
    """Suggest people to connect with based on shared interests and location."""
    # Get accounts already linked
    existing = Link.query.filter(
        or_(Link.requester_id == account_id, Link.addressee_id == account_id)
    ).all()
    linked_ids = set()
    for l in existing:
        linked_ids.add(l.requester_id)
        linked_ids.add(l.addressee_id)

    # Get own tag IDs
    my_tags = {ip.tag_id for ip in InterestProfile.query.filter_by(account_id=account_id).all()}

    # Find accounts with overlapping interest tags
    if my_tags:
        shared_interest_accounts = InterestProfile.query.filter(
            InterestProfile.tag_id.in_(my_tags),
            InterestProfile.account_id != account_id,
            ~InterestProfile.account_id.in_(linked_ids) if linked_ids else True
        ).with_entities(InterestProfile.account_id).distinct().limit(limit * 2).all()
        candidate_ids = [row[0] for row in shared_interest_accounts]
    else:
        candidate_ids = []

    # Fallback: recent active accounts
    if len(candidate_ids) < limit:
        fallback = Account.query.filter(
            Account.id != account_id,
            Account.account_status == 'active',
            Account.deleted_at.is_(None),
            ~Account.id.in_(linked_ids | set(candidate_ids)) if (linked_ids or candidate_ids) else True
        ).order_by(Account.created_at.desc()).limit(limit - len(candidate_ids)).all()
        candidate_ids.extend([a.id for a in fallback])

    accounts = Account.query.filter(
        Account.id.in_(candidate_ids[:limit]),
        Account.deleted_at.is_(None),
    ).all()
    return [a.to_dict() for a in accounts]
