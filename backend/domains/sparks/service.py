"""
Sparks service: deck generation, match creation.
"""
import uuid
from sqlalchemy import or_
from backend.models import db
from backend.domains.sparks.models import Spark, Match
from backend.domains.identity.models import Account
from backend.domains.profile.models import DatingProfile


def get_deck(account_id: str, limit: int = 20) -> list:
    """Generate a discovery deck of profiles to swipe on."""
    # Exclude accounts already acted on and blocked accounts
    acted_ids = {
        s.target_id for s in Spark.query.filter_by(actor_id=account_id).all()
    }
    acted_ids.add(account_id)

    # Get accounts with dating profiles who have sparks mode enabled
    query = db.session.query(Account).join(
        DatingProfile, DatingProfile.account_id == Account.id
    ).filter(
        Account.id.notin_(acted_ids) if acted_ids else True,
        Account.account_status == 'active',
        Account.deleted_at.is_(None),
    ).order_by(Account.created_at.desc()).limit(limit)

    accounts = query.all()
    result = []
    for acc in accounts:
        # Only include accounts with sparks mode enabled
        modes = acc.modes_enabled or {}
        if isinstance(modes, str):
            import json
            try:
                modes = json.loads(modes)
            except Exception:
                modes = {}
        if not modes.get('sparks', False):
            continue
        dating = DatingProfile.query.filter_by(account_id=acc.id).first()
        card = acc.to_dict()
        card['dating_profile'] = dating.to_dict() if dating else None
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
