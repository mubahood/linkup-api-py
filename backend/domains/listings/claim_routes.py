"""
Public claim routes: /v1/listings/*

No admin auth here by design — the whole point is a real, not-yet-registered
person can find and claim their own listing. Security instead comes from:
  - claim_id being an unguessable UUID (capability-token model, same as a
    magic-link flow) — knowing it is what lets you act on that one claim.
  - the OTP step itself (existing lu_otp_requests expiry/attempt limits).
  - ClaimError (bad state/input) always maps to 400, never a 500 that could
    leak internals.

See PROFILE_CLAIM_IMPORTER_PLAN.md §4-5 and claim_service.py for the design
this implements.
"""
from flask import Blueprint, request

from backend.shared.utils.response import success_response, error_response, paginated_response
from backend.domains.listings.claim_service import ListingClaimService, ClaimError

listing_claims_bp = Blueprint('v1_listing_claims', __name__, url_prefix='/v1/listings')


@listing_claims_bp.route('/search', methods=['GET'])
def search_listings():
    """?source=&location=&page=&per_page= — only returns listings still open to claim."""
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=20, type=int)
    source = request.args.get('source')
    location = request.args.get('location')

    items, total, current_page, last_page, per_page = ListingClaimService.search_listings(
        source=source, location_text=location, page=page, per_page=per_page,
    )
    return paginated_response(items, total, current_page, per_page)


@listing_claims_bp.route('/claims', methods=['POST'])
def start_claim():
    """{source_listing_id, phone} -> {claim_id, status}. Idempotent: a second
    call for a listing already being claimed returns the existing claim."""
    data = request.get_json(silent=True) or {}
    source_listing_id = (data.get('source_listing_id') or '').strip()
    phone = (data.get('phone') or '').strip()

    if not source_listing_id or not phone:
        return error_response('source_listing_id and phone are required.', status_code=400)

    try:
        claim = ListingClaimService.start_claim(source_listing_id, phone)
    except ClaimError as e:
        return error_response(str(e), status_code=400)

    return success_response('Claim started.', {'claim_id': claim.id, 'status': claim.status})


@listing_claims_bp.route('/claims/<claim_id>', methods=['GET'])
def get_claim_status(claim_id):
    """Minimal status check — the claim_id itself is the access control."""
    from backend.domains.listings.models import ListingClaim
    claim = ListingClaim.query.get(claim_id)
    if claim is None:
        return error_response('Claim not found.', status_code=404)
    return success_response('Claim status retrieved.', {
        'claim_id': claim.id, 'status': claim.status,
        'liveness_submitted': bool(claim.liveness_capture_path),
    })


@listing_claims_bp.route('/claims/<claim_id>/otp/request', methods=['POST'])
def request_otp(claim_id):
    try:
        ListingClaimService.request_otp(claim_id)
    except ClaimError as e:
        return error_response(str(e), status_code=400)
    return success_response('OTP sent.')


@listing_claims_bp.route('/claims/<claim_id>/otp/verify', methods=['POST'])
def verify_otp(claim_id):
    data = request.get_json(silent=True) or {}
    code = (data.get('code') or '').strip()
    if not code:
        return error_response('code is required.', status_code=400)

    try:
        ok, message = ListingClaimService.verify_otp_step(claim_id, code)
    except ClaimError as e:
        return error_response(str(e), status_code=400)

    if not ok:
        return error_response(message, status_code=400)
    return success_response(message)


@listing_claims_bp.route('/claims/<claim_id>/liveness', methods=['POST'])
def submit_liveness(claim_id):
    """Multipart upload, field name 'capture'."""
    file = request.files.get('capture')
    if not file:
        return error_response('capture file is required.', status_code=400)

    try:
        claim = ListingClaimService.submit_liveness_capture(claim_id, file)
    except ClaimError as e:
        return error_response(str(e), status_code=400)

    return success_response('Liveness capture submitted — awaiting review.', {'status': claim.status})
