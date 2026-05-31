"""
Sparks service: deck generation, match creation.
"""
import uuid
from sqlalchemy import or_
from backend.models import db
from backend.domains.sparks.models import Spark, Match
from backend.domains.identity.models import Account
from backend.domains.profile.models import DatingProfile


def get_deck(account_id: str, limit: int = 20, allow_passed: bool = False) -> list:
    """
    Generate a discovery deck ordered by Interest Graph compatibility.

    Excludes:
    - Already acted-on profiles
    - Blocked accounts (both directions)
    - Heavily-reported accounts
    - Self
    - Paused / incognito profiles (discoverability)

    Filters:
    - Actor's age preference vs candidate's birth_year
    - Candidate's age preference vs actor's birth_year
    - Gender preference (soft match — never hard-reject if no preference set)
    """
    import json
    from datetime import date
    from backend.domains.safety.models import Block, Report
    from backend.shared.scoring.interest_graph import rank_candidates

    # Determine exclusion set:
    # allow_passed=True → only exclude spark_up/standout (matches), not pass actions
    if allow_passed:
        # Only exclude positive actions — allow re-discovery of passed profiles
        acted_ids = {
            s.target_id for s in Spark.query.filter_by(actor_id=account_id).filter(
                Spark.action.in_(['spark_up', 'standout'])
            ).all()
        }
    else:
        acted_ids = {s.target_id for s in Spark.query.filter_by(actor_id=account_id).all()}

    blocked_ids = (
        {b.blocked_id for b in Block.query.filter_by(blocker_id=account_id).all()} |
        {b.blocker_id for b in Block.query.filter_by(blocked_id=account_id).all()}
    )
    # Heavily-reported accounts (reported ≥3 times) get excluded from deck
    from sqlalchemy import func
    reported_counts = (
        db.session.query(Report.target_account_id, func.count(Report.id).label('cnt'))
        .group_by(Report.target_account_id)
        .having(func.count(Report.id) >= 3)
        .all()
    )
    reported_ids = {row[0] for row in reported_counts}

    excluded = acted_ids | blocked_ids | reported_ids | {account_id}

    # Fetch a wider pool (5× limit) to allow filtering + scoring
    pool_size = limit * 5
    query = db.session.query(Account, DatingProfile).join(
        DatingProfile, DatingProfile.account_id == Account.id
    ).filter(
        Account.id.notin_(excluded) if excluded else True,
        Account.account_status == 'active',
        Account.deleted_at.is_(None),
        DatingProfile.discoverability == 'discoverable',  # paused/incognito excluded
    ).limit(pool_size)
    rows = query.all()

    # Load actor's own dating profile for preference matching
    actor_dating = DatingProfile.query.filter_by(account_id=account_id).first()
    actor_birth_year = actor_dating.birth_year if actor_dating else None
    actor_age = (date.today().year - actor_birth_year) if actor_birth_year else None
    actor_gender = actor_dating.gender if actor_dating else None
    actor_age_min = actor_dating.age_min if actor_dating else 18
    actor_age_max = actor_dating.age_max if actor_dating else 99
    actor_looking_for = actor_dating.looking_for_gender if actor_dating else None

    current_year = date.today().year

    sparks_accounts = []
    dating_map: dict = {}

    for acc, dp in rows:
        # Check sparks mode enabled
        modes = acc.modes_enabled or {}
        if isinstance(modes, str):
            try:
                modes = json.loads(modes)
            except Exception:
                modes = {}
        if not modes.get('sparks', False):
            continue

        # Age preference filter (soft — skip if no birth_year data)
        if dp.birth_year:
            candidate_age = current_year - dp.birth_year
            # Actor's preference: is candidate within actor's preferred age range?
            if candidate_age < actor_age_min or candidate_age > actor_age_max:
                continue
            # Candidate's preference: is actor within candidate's preferred range?
            if actor_age:
                cand_min = dp.age_min or 18
                cand_max = dp.age_max or 99
                if actor_age < cand_min or actor_age > cand_max:
                    continue

        # Gender preference filter (soft — only apply if both sides set preferences)
        if actor_looking_for and dp.gender:
            if actor_looking_for.lower() not in ('any', 'all', '') and \
               dp.gender.lower() != actor_looking_for.lower():
                continue
        if dp.looking_for_gender and actor_gender:
            if dp.looking_for_gender.lower() not in ('any', 'all', '') and \
               actor_gender.lower() != dp.looking_for_gender.lower():
                continue

        sparks_accounts.append(acc)
        dating_map[acc.id] = dp

    if not sparks_accounts:
        return []

    # Rank by Interest Graph overlap (dating mode)
    candidate_ids = [acc.id for acc in sparks_accounts]
    ranked = rank_candidates(account_id, candidate_ids, mode='dating')

    # Build result in ranked order (up to limit)
    acc_map = {acc.id: acc for acc in sparks_accounts}

    result = []
    for cid, score in ranked[:limit]:
        acc = acc_map.get(cid)
        if not acc:
            continue
        card = acc.to_dict()
        dating = dating_map.get(cid)
        card['dating_profile'] = dating.to_dict() if dating else None
        card['compatibility_score'] = round(score, 3)
        result.append(card)
    return result


def record_action(actor_id: str, target_id: str, action: str) -> tuple[Spark, Match | None]:
    """Record a spark action and check for a mutual match."""
    # Upsert the spark (on duplicate, update action)
    existing = Spark.query.filter_by(actor_id=actor_id, target_id=target_id).first()
    if existing:
        existing.action = action
        spark = existing
    else:
        spark = Spark(
            id=str(uuid.uuid4()),
            actor_id=actor_id,
            target_id=target_id,
            action=action,
        )
        db.session.add(spark)

    db.session.flush()

    match = None
    if action in ('spark_up', 'standout'):
        # Check if target has sparked back
        reverse = Spark.query.filter_by(
            actor_id=target_id, target_id=actor_id
        ).filter(Spark.action.in_(['spark_up', 'standout'])).first()

        if reverse:
            # Check no existing match
            existing_match = Match.query.filter(
                or_(
                    (Match.account_a_id == actor_id) & (Match.account_b_id == target_id),
                    (Match.account_a_id == target_id) & (Match.account_b_id == actor_id),
                )
            ).first()
            if not existing_match:
                match = Match(
                    id=str(uuid.uuid4()),
                    account_a_id=actor_id,
                    account_b_id=target_id,
                    spark_a_id=spark.id,
                    spark_b_id=reverse.id,
                )
                db.session.add(match)
                db.session.flush()
                # Auto-create a Sparks direct thread for the match
                _create_match_thread(match, actor_id, target_id)

    db.session.commit()
    return spark, match


def _create_match_thread(match: Match, account_a: str, account_b: str):
    """Create a Sparks-mode direct thread for a new match."""
    from datetime import datetime
    from backend.domains.chat.models import Thread, ThreadParticipant
    thread = Thread(
        id=str(uuid.uuid4()),
        type='spark',
        mode='dating',
        created_by=account_a,
        last_message_at=datetime.utcnow(),
    )
    db.session.add(thread)
    db.session.flush()
    for pid in [account_a, account_b]:
        db.session.add(ThreadParticipant(
            id=str(uuid.uuid4()),
            thread_id=thread.id,
            account_id=pid,
        ))
    match.thread_id = thread.id
