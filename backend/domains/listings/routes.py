"""
Listings domain routes: /v1/admin/listings/*

Phase 1-2 scope: read-only discovery visibility for admins. There is no
crawl-trigger endpoint yet (Phase 3 adds source adapters; Phase 12 adds
scheduled/manual crawling) and no public claim-search endpoint yet (Phase 4).

All endpoints require is_admin=1, matching the existing admin-gating pattern
used across the codebase (see domains/admin/routes.py::_admin_required) —
duplicated locally rather than imported, per that same existing convention.
"""
from functools import wraps

from flask import Blueprint, request

from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.utils.response import success_response, error_response, paginated_response
from backend.domains.listings.service import ListingService

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
