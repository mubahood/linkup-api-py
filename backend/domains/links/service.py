"""
Links service: suggestion logic using Interest Graph scoring.
"""
from sqlalchemy import or_
from backend.domains.links.models import Link
from backend.domains.identity.models import Account
from backend.domains.interest.models import InterestProfile
from backend.domains.safety.models import Block


def get_link_suggestions(account_id: str, limit: int = 10) -> list:
    """
    Suggest people to connect with, ranked by professional Interest Graph overlap.
    Excludes: already linked, blocked (both directions), self.
    """
    from backend.shared.scoring.interest_graph import rank_candidates

    # Collect excluded IDs
    existing = Link.query.filter(
        or_(Link.requester_id == account_id, Link.addressee_id == account_id)
    ).all()
    linked_ids = {l.requester_id for l in existing} | {l.addressee_id for l in existing}

    blocked_ids = (
        {b.blocked_id for b in Block.query.filter_by(blocker_id=account_id).all()} |
        {b.blocker_id for b in Block.query.filter_by(blocked_id=account_id).all()}
    )
    excluded = linked_ids | blocked_ids | {account_id}

    # Gather candidate pool from shared interest tags (wider pool for scoring)
    pool_size = limit * 4
    my_tags = {ip.tag_id for ip in InterestProfile.query.filter_by(account_id=account_id).all()}

    if my_tags:
        shared = InterestProfile.query.filter(
            InterestProfile.tag_id.in_(my_tags),
            InterestProfile.account_id != account_id,
            ~InterestProfile.account_id.in_(excluded) if excluded else True,
        ).with_entities(InterestProfile.account_id).distinct().limit(pool_size).all()
        candidate_ids = [row[0] for row in shared]
    else:
        candidate_ids = []

    # Fallback: active accounts not yet collected
    if len(candidate_ids) < pool_size:
        fallback = Account.query.filter(
            Account.id != account_id,
            Account.account_status == 'active',
            Account.deleted_at.is_(None),
            ~Account.id.in_(excluded | set(candidate_ids)) if (excluded or candidate_ids) else True,
        ).order_by(Account.created_at.desc()).limit(pool_size - len(candidate_ids)).all()
        candidate_ids.extend([a.id for a in fallback])

    if not candidate_ids:
        return []

    # Rank by Interest Graph overlap (professional mode)
    ranked = rank_candidates(account_id, candidate_ids[:pool_size], mode='professional')

    # Fetch and return top-N accounts in ranked order
    acc_map = {
        a.id: a for a in Account.query.filter(
            Account.id.in_([cid for cid, _ in ranked[:limit]]),
            Account.deleted_at.is_(None),
        ).all()
    }

    result = []
    for cid, score in ranked[:limit]:
        acc = acc_map.get(cid)
        if not acc:
            continue
        d = acc.to_dict()
        d['compatibility_score'] = round(score, 3)
        result.append(d)
    return result
