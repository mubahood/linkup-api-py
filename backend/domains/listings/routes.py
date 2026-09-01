"""
Listings domain routes: /v1/admin/listings/*

Discovery visibility (Phase 1-2) plus admin-side claim review (Phase 4-6).
There is no crawl-trigger endpoint yet (Phase 12 adds scheduled/manual
crawling) — and no adapter to trigger it against right now regardless (both
configured sources are 'unavailable', see service.py's SOURCE_REGISTRY).

All endpoints require is_admin=1, matching the existing admin-gating pattern
used across the codebase (see domains/admin/routes.py::_admin_required) —
duplicated locally rather than imported, per that same existing convention.

The public, unauthenticated claim endpoints (search/start/verify) live in
claim_routes.py, not here — a not-yet-registered person must be able to
claim their own listing without admin credentials.
"""
from functools import wraps

from flask import Blueprint, request

from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.utils.response import success_response, error_response, paginated_response
from backend.domains.listings.service import ListingService
from backend.domains.listings.claim_service import ListingClaimService, ClaimError

listings_bp = Blueprint('v1_admin_listings', __name__, url_prefix='/v1/admin/listings')


def _admin_required(fn):
    """Decorator: require is_admin=1."""
    @wraps(fn)
    @lu_jwt_required
    def wrapper(account, *args, **kwargs):
        if not account.is_admin:
            return error_response('Admin access required.', status_code=403)
        return fn(account, *args, **kwargs)
    return wrapper


@listings_bp.route('/sources', methods=['GET'])
@_admin_required
def list_sources(account):
    """Configured source registry + live discovery/crawl stats per source."""
    return success_response('Sources retrieved.', ListingService.list_sources())


@listings_bp.route('/discovered', methods=['GET'])
@_admin_required
def list_discovered(account):
    """Paginated discovery-stage listings. ?source=&claim_status=&page=&per_page="""
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=20, type=int)
    source = request.args.get('source')
    claim_status = request.args.get('claim_status')

    items, total, current_page, last_page, per_page = ListingService.list_discovered(
        source=source, claim_status=claim_status, page=page, per_page=per_page,
    )
    return paginated_response(items, total, current_page, per_page)


@listings_bp.route('/claims', methods=['GET'])
@_admin_required
def list_claims(account):
    """Paginated claims. ?status=&page=&per_page="""
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=20, type=int)
    status = request.args.get('status')

    items, total, current_page, last_page, per_page = ListingClaimService.list_claims(
        status=status, page=page, per_page=per_page,
    )
    return paginated_response(items, total, current_page, per_page)


@listings_bp.route('/claims/<claim_id>/review-liveness', methods=['POST'])
@_admin_required
def review_liveness(account, claim_id):
    """{passed: bool, notes?: str}. This is ONE of two required verification
    events — it never authorizes a claim by itself (see claim_service.py)."""
    data = request.get_json(silent=True) or {}
    if 'passed' not in data:
        return error_response('passed is required.', status_code=400)

    try:
        claim = ListingClaimService.admin_review_liveness(
            claim_id, account, passed=bool(data['passed']), notes=data.get('notes'),
        )
    except ClaimError as e:
        return error_response(str(e), status_code=400)

    return success_response('Liveness review recorded.', claim.to_dict())


@listings_bp.route('/claims/<claim_id>/transition', methods=['POST'])
@_admin_required
def transition_claim(account, claim_id):
    """{status: str, reason?: str}. Only transitions in
    claim_service.ADMIN_ALLOWED_TRANSITIONS are permitted — 'authorized' is
    not a reachable destination through this endpoint under any input."""
    data = request.get_json(silent=True) or {}
    new_status = (data.get('status') or '').strip()
    if not new_status:
        return error_response('status is required.', status_code=400)

    try:
        claim = ListingClaimService.admin_transition(
            claim_id, new_status, account, reason=data.get('reason'),
        )
    except ClaimError as e:
        return error_response(str(e), status_code=400)

    return success_response('Claim transitioned.', claim.to_dict())
