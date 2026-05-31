"""
Sparks routes: /v1/sparks/*
Mode-protected: account must have sparks enabled.
"""
from flask import Blueprint, request
from sqlalchemy import or_
from backend.models import db
from backend.domains.sparks.models import Spark, Match
from backend.domains.sparks.service import get_deck, record_action
from backend.shared.auth.decorators import sparks_mode_required, lu_jwt_required
from backend.shared.utils.response import success_response, error_response, paginated_response
from backend.shared.utils.pagination import paginate_query

sparks_bp = Blueprint('v1_sparks', __name__, url_prefix='/v1/sparks')


@sparks_bp.route('/deck', methods=['GET'])
@sparks_mode_required
def deck(account):
    """
    Get discovery deck.
    ?refresh=true — include previously-passed profiles (deck re-discovery).
    """
    limit = request.args.get('limit', 20, type=int)
    refresh = request.args.get('refresh', '').lower() == 'true'
    cards = get_deck(account.id, limit=limit, allow_passed=refresh)
    return success_response('Deck loaded.', cards)


@sparks_bp.route('/action', methods=['POST'])
@sparks_mode_required
def action(account):
    """Record a swipe action."""
    data = request.get_json(silent=True) or {}
    target_id = data.get('target_id', '').strip()
    act = data.get('action', '').strip()

    if not target_id or not act:
        return error_response('target_id and action are required.')
    if act not in ('spark_up', 'pass', 'standout', 'undo'):
        return error_response('Invalid action. Use: spark_up, pass, standout, undo.')
    if target_id == account.id:
        return error_response('You cannot spark yourself.')

    spark, match = record_action(account.id, target_id, act)

    # Notify on match
    if match:
        try:
            from backend.domains.notifications.service import create_notification
            from backend.domains.identity.models import Account
            actor_acct = Account.query.get(account.id)
            target_acct = Account.query.get(target_id)
            if actor_acct and target_acct:
                for notif_target, other in [
                    (account.id, target_acct.display_name),
                    (target_id, actor_acct.display_name),
                ]:
                    create_notification(
                        account_id=notif_target,
                        notif_type='spark.match',
                        title=f"You matched with {other}! 🎉",
                        body="Say hello — don't be shy.",
                        data={'match_id': match.id},
                        action_url=f'/sparks/matches/{match.id}',
                    )
        except Exception:
            pass

    return success_response(
        "It's a match! 🎉" if match else 'Action recorded.',
        {
            'spark': spark.to_dict(),
            'match': match.to_dict(account.id) if match else None,
            'is_match': bool(match),
        }
    )


@sparks_bp.route('/matches', methods=['GET'])
@sparks_mode_required
def matches(account):
    """List all matches."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = Match.query.filter(
        or_(Match.account_a_id == account.id, Match.account_b_id == account.id)
    ).order_by(Match.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([m.to_dict(account.id) for m in items], total, page, per_page, 'Matches loaded.')


@sparks_bp.route('/matches/<match_id>/unmatch', methods=['POST'])
@sparks_mode_required
def unmatch(account, match_id):
    """Unmatch — ends the match and removes from each other's matches list."""
    match = Match.query.filter(
        Match.id == match_id,
        or_(Match.account_a_id == account.id, Match.account_b_id == account.id),
        Match.state == 'active',
    ).first()
    if not match:
        return error_response('Active match not found.', status_code=404)
    from datetime import datetime
    match.state = 'unmatched'
    match.unmatched_by = account.id
    match.unmatched_at = datetime.utcnow()
    db.session.commit()
    # Notify the other person
    other_id = match.account_b_id if account.id == match.account_a_id else match.account_a_id
    try:
        from backend.domains.notifications.service import create_notification
        create_notification(
            account_id=other_id,
            notif_type='spark.unmatched',
            title='You have been unmatched',
            body='This match is no longer active.',
            data={'match_id': match_id},
            action_url='/sparks/matches',
        )
    except Exception:
        pass
    return success_response('Unmatched successfully.')


@sparks_bp.route('/matches/<match_id>/met', methods=['POST'])
@sparks_mode_required
def mark_met(account, match_id):
    """Signal that you met this person in real life — ML outcome feedback."""
    match = Match.query.filter(
        Match.id == match_id,
        or_(Match.account_a_id == account.id, Match.account_b_id == account.id),
        Match.state == 'active',
    ).first()
    if not match:
        return error_response('Active match not found.', status_code=404)
    from datetime import datetime
    if not match.met_at:
        match.met_at = datetime.utcnow()
        db.session.commit()
    return success_response('Meeting recorded.', match.to_dict(account.id))


@sparks_bp.route('/matches/<match_id>', methods=['GET'])
@sparks_mode_required
def match_detail(account, match_id):
    match = Match.query.filter(
        Match.id == match_id,
        or_(Match.account_a_id == account.id, Match.account_b_id == account.id)
    ).first()
    if not match:
        return error_response('Match not found.', status_code=404)
    return success_response('Match loaded.', match.to_dict(account.id))
