"""
Interest routes: /v1/interests/*
"""
import uuid
from flask import Blueprint, request
from backend.models import db
from backend.domains.interest.models import InterestTag, InterestProfile
from backend.domains.interest.service import get_taxonomy, get_suggestions, apply_decay
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.utils.response import success_response, error_response

interest_bp = Blueprint('v1_interest', __name__, url_prefix='/v1/interests')


@interest_bp.route('/taxonomy', methods=['GET'])
def taxonomy():
    """Full interest taxonomy grouped by dimension."""
    return success_response('Taxonomy loaded.', get_taxonomy())


@interest_bp.route('/search', methods=['GET'])
def search():
    """Search interest tags by keyword."""
    q = request.args.get('q', '').strip()
    dimension = request.args.get('dimension', '')
    if not q:
        return error_response('Search query q is required.')
    query = InterestTag.query.filter(
        InterestTag.display_name_en.ilike(f'%{q}%')
    )
    if dimension:
        query = query.filter(InterestTag.dimension == dimension)
    tags = query.order_by(InterestTag.popularity.desc()).limit(30).all()
    return success_response('Tags found.', [t.to_dict() for t in tags])


@interest_bp.route('/me', methods=['GET'])
@lu_jwt_required
def my_interests(account):
    """Get my interest weights with on-read decay applied."""
    show_decay = request.args.get('with_decay', '').lower() == 'true'
    profiles = InterestProfile.query.filter_by(account_id=account.id).all()
    result = []
    for p in profiles:
        d = p.to_dict()
        if show_decay:
            d['effective_weight'] = apply_decay(p)
        result.append(d)
    return success_response('Interests loaded.', result)


@interest_bp.route('/me', methods=['POST'])
@lu_jwt_required
def set_interests(account):
    """Bulk set/update interests. Expects {interests: [{tag_id, weight?, mode?, pinned?}]}"""
    data = request.get_json(silent=True) or {}
    interests = data.get('interests', [])
    if not interests:
        return error_response('interests array is required.')

    results = []
    for item in interests:
        tag_id = item.get('tag_id')
        slug = item.get('slug')
        # Support slug-based lookup if tag_id not provided
        if not tag_id and slug:
            tag = InterestTag.query.filter_by(slug=slug).first()
            tag_id = tag.id if tag else None
        if not tag_id:
            continue
        tag = db.session.get(InterestTag, tag_id)
        if not tag:
            continue
        existing = InterestProfile.query.filter_by(
            account_id=account.id, tag_id=tag_id
        ).first()
        if existing:
            existing.weight = item.get('weight', existing.weight)
            existing.mode = item.get('mode', existing.mode)
            existing.pinned = int(item.get('pinned', existing.pinned))
            results.append(existing.to_dict())
        else:
            ip = InterestProfile(
                id=str(uuid.uuid4()),
                account_id=account.id,
                tag_id=tag_id,
                weight=item.get('weight', 0.5),
                mode=item.get('mode', 'professional'),
                pinned=int(item.get('pinned', 0)),
                source='explicit',
            )
            db.session.add(ip)
            results.append(ip.to_dict())

    db.session.commit()
    return success_response('Interests updated.', {
        'updated': len(results),
        'interests': results,
    })


@interest_bp.route('/me/<tag_id>', methods=['DELETE'])
@lu_jwt_required
def remove_interest(account, tag_id):
    """Remove an interest."""
    ip = InterestProfile.query.filter_by(account_id=account.id, tag_id=tag_id).first()
    if not ip:
        return error_response('Interest not found.', status_code=404)
    db.session.delete(ip)
    db.session.commit()
    return success_response('Interest removed.')


@interest_bp.route('/signal', methods=['POST'])
@lu_jwt_required
def signal_interest(account):
    """
    Behavioral interest reinforcement signal.

    The mobile app calls this when a user meaningfully engages with content
    (e.g. clicks into a job, views a hub, opens a profile).

    Body: {
      "tag_id": "<uuid>",          # interest tag that was signaled
      "source": "job_view",        # event type: job_view | hub_visit | profile_view | search_click | ...
      "strength": 0.1              # reinforcement magnitude 0–1 (default 0.1)
    }

    Behavior:
    - If the tag exists in the user's profile, add `strength` to weight (capped at 1.0)
    - If not present, create a new implicit interest with weight=`strength`, source='inferred_behavior'
    - Pinned interests are never modified
    """
    data = request.get_json(silent=True) or {}
    tag_id = (data.get('tag_id') or '').strip()
    source = (data.get('source') or 'behavior').strip()[:30]
    strength = min(max(float(data.get('strength', 0.1)), 0.0), 1.0)

    if not tag_id:
        return error_response('tag_id is required.')

    tag = db.session.get(InterestTag, tag_id)
    if not tag:
        return error_response('Interest tag not found.', status_code=404)

    from datetime import datetime
    ip = InterestProfile.query.filter_by(account_id=account.id, tag_id=tag_id).first()
    if ip:
        if not ip.pinned:
            ip.weight = min(1.0, float(ip.weight or 0.5) + strength)
            ip.source = 'behavioral' if ip.source not in ('explicit',) else ip.source
            ip.last_signaled = datetime.utcnow()
        return success_response('Interest reinforced.', ip.to_dict())
    else:
        ip = InterestProfile(
            id=str(uuid.uuid4()),
            account_id=account.id,
            tag_id=tag_id,
            weight=strength,
            mode='professional',
            source='behavioral',
            last_signaled=datetime.utcnow(),
        )
        db.session.add(ip)

    # Increment tag popularity counter
    if tag.popularity is not None:
        tag.popularity = tag.popularity + 1

    db.session.commit()
    return success_response('Interest signal recorded.', ip.to_dict(), status_code=201)


@interest_bp.route('/suggestions', methods=['GET'])
@lu_jwt_required
def suggestions(account):
    """Suggested interests based on profile."""
    return success_response('Suggestions loaded.', get_suggestions(account.id))
