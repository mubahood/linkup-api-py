"""
Interest routes: /v1/interests/*
"""
import uuid
from flask import Blueprint, request
from backend.models import db
from backend.domains.interest.models import InterestTag, InterestProfile
from backend.domains.interest.service import get_taxonomy, get_suggestions
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
    """Get my interest weights."""
    profiles = InterestProfile.query.filter_by(account_id=account.id).all()
    return success_response('Interests loaded.', [p.to_dict() for p in profiles])


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
                mode=item.get('mode', 'both'),
                pinned=int(item.get('pinned', 0)),
                source='explicit',
            )
            db.session.add(ip)
            results.append(ip.to_dict())

    db.session.commit()
    return success_response('Interests updated.', results)


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


@interest_bp.route('/suggestions', methods=['GET'])
@lu_jwt_required
def suggestions(account):
    """Suggested interests based on profile."""
    return success_response('Suggestions loaded.', get_suggestions(account.id))
