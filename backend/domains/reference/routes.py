"""
Reference routes: /v1/reference/*
"""
import uuid
from flask import Blueprint, request
from backend.models import db
from backend.domains.reference.models import Location, Institution, Org
from backend.shared.utils.response import success_response, error_response

reference_bp = Blueprint('v1_reference', __name__, url_prefix='/v1/reference')


@reference_bp.route('/locations', methods=['GET'])
def locations():
    q         = request.args.get('q', '')
    level     = request.args.get('level', '')
    parent_id = request.args.get('parent_id', '')
    query = Location.query
    if q:         query = query.filter(Location.name.ilike(f'%{q}%'))
    if level:     query = query.filter(Location.level == level)
    if parent_id: query = query.filter(Location.parent_id == parent_id)  # cascade (P-API-02)
    items = query.order_by(Location.name).limit(200).all()
    return success_response('Locations loaded.', [i.to_dict() for i in items])


@reference_bp.route('/dating-options', methods=['GET'])
def dating_options():
    """Canonical dropdown catalog for the dating profile + preference wizards (P-API-01).
    ?include_sensitive=false hides match-only catalogs (tribe, politics)."""
    from backend.domains.reference.dating_options import get_catalog
    include_sensitive = request.args.get('include_sensitive', 'true').lower() != 'false'
    return success_response('Dating options loaded.', get_catalog(include_sensitive))


@reference_bp.route('/institutions', methods=['GET'])
def institutions():
    """
    GET /v1/reference/institutions
    Params:
      q        — search name / short_name
      type     — filter by type (university | institute | college | professional_body)
      popular  — "true" → only is_popular=1 entries
      limit    — max results (default 50, max 200)
      offset   — pagination offset
    Returns list sorted by sort_order (most popular first), then name.
    """
    q       = request.args.get('q', '').strip()
    itype   = request.args.get('type', '').strip()
    popular = request.args.get('popular', '').lower() == 'true'
    limit   = min(int(request.args.get('limit', 50)), 200)
    offset  = int(request.args.get('offset', 0))

    query = Institution.query

    if q:
        query = query.filter(
            db.or_(
                Institution.name.ilike(f'%{q}%'),
                Institution.short_name.ilike(f'%{q}%'),
            )
        )
    if itype:
        query = query.filter(Institution.type == itype)
    if popular:
        query = query.filter(Institution.is_popular == 1)

    query = query.order_by(Institution.sort_order, Institution.name)
    total = query.count()
    items = query.offset(offset).limit(limit).all()

    # Resolve matching interest tag IDs so the mobile picker can work
    # with the existing interests system without extra API calls.
    from backend.domains.interest.models import InterestTag
    tag_map = {}  # institution name (lower) → tag id
    tags = InterestTag.query.filter_by(dimension='education_affiliation').all()
    for t in tags:
        tag_map[t.display_name_en.lower()] = t.id

    return success_response('Institutions loaded.', {
        'total': total,
        'items': [_inst_dict(i, tag_map) for i in items],
    })


@reference_bp.route('/institutions/suggest', methods=['POST'])
def suggest_institution():
    """
    POST /v1/reference/institutions/suggest
    Body: { name, type?, district?, website? }
    Lets users add institutions not yet in the reference DB.
    Saves with verified=0 for admin review.
    """
    data    = request.get_json(silent=True) or {}
    name    = (data.get('name') or '').strip()
    if not name or len(name) < 3:
        return error_response('Institution name must be at least 3 characters.')
    if len(name) > 300:
        return error_response('Name too long (max 300 characters).')

    # Avoid near-duplicate suggestions
    existing = Institution.query.filter(
        Institution.name.ilike(name)
    ).first()
    if existing:
        return success_response('Institution already exists.', _inst_dict(existing))

    inst = Institution(
        id=str(uuid.uuid4()),
        name=name,
        short_name=data.get('short_name', ''),
        type=data.get('type', 'university'),
        country='Uganda',
        district=data.get('district', ''),
        website=data.get('website', ''),
        verified=0,
        sort_order=999,
        is_popular=0,
    )
    db.session.add(inst)
    db.session.commit()

    return success_response(
        'Institution submitted for review. Thank you!',
        _inst_dict(inst),
        status_code=201,
    )


@reference_bp.route('/orgs', methods=['GET'])
def orgs():
    q     = request.args.get('q', '')
    limit = min(int(request.args.get('limit', 50)), 200)
    query = Org.query
    if q:
        query = query.filter(
            db.or_(
                Org.name.ilike(f'%{q}%'),
                Org.industry.ilike(f'%{q}%'),
            )
        )
    items = query.order_by(Org.name).limit(limit).all()
    return success_response('Organisations loaded.', [i.to_dict() for i in items])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _inst_dict(inst: Institution, tag_map: dict = None) -> dict:
    tag_id = None
    if tag_map is not None:
        tag_id = tag_map.get(inst.name.lower())
    return {
        'id':         inst.id,
        'name':       inst.name,
        'short_name': inst.short_name,
        'type':       inst.type,
        'district':   inst.district,
        'website':    inst.website,
        'verified':   bool(inst.verified),
        'is_popular': bool(getattr(inst, 'is_popular', False)),
        'sort_order': getattr(inst, 'sort_order', 100),
        'tag_id':     tag_id,   # interest tag ID; may be null for user-suggested entries
    }
