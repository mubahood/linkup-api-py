"""
Claim + verification + authorization-state-machine service (Phase 4-6 of
PROFILE_CLAIM_IMPORTER_PLAN.md).

The one invariant everything here exists to protect: a claim can only reach
`authorized` by passing BOTH an `otp` verification event and a
`liveness_match` verification event. `_try_authorize()` is the only place
that ever sets `authorized_at`/`status='authorized'`, and nothing exposed to
an admin route can reach it directly — see `ADMIN_ALLOWED_TRANSITIONS` and
`admin_transition()`.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from backend.models import db
from backend.domains.listings.models import ListingClaim, ClaimVerificationEvent
from backend.domains.listings.models import SourceListing

logger = logging.getLogger(__name__)

# Listing claim_status values a listing must be in for a new claim to start.
CLAIMABLE_LISTING_STATUSES = {'discovered', 'claim_available'}

# Claim statuses that count as "already in progress" — used to block a second
# concurrent claim on the same listing, not to block re-claiming after a
# terminal outcome (rejected/removed).
ACTIVE_CLAIM_STATUSES = {
    'claim_requested', 'verification_pending', 'verified', 'authorized',
    'importing', 'imported', 'user_review', 'published',
}

# (from_status, to_status) pairs an admin route may trigger. Notably absent:
# anything landing on 'authorized' — that transition is system_only, reached
# only via _try_authorize() after both verification events exist. This set is
# the enforcement mechanism, not just documentation — admin_transition()
# checks against it and every admin-facing route goes through
# admin_transition(), never through _set_status() directly.
ADMIN_ALLOWED_TRANSITIONS = {
    ('claim_requested', 'rejected'),
    ('verification_pending', 'rejected'),
    ('verified', 'rejected'),
    ('authorized', 'rejected'),
    ('imported', 'user_review'),
    ('user_review', 'published'),
    ('user_review', 'rejected'),
    ('authorized', 'removal_requested'),
    ('published', 'removal_requested'),
    ('removal_requested', 'removed'),
}


class ClaimError(ValueError):
    """Raised for any invalid claim operation — bad state, bad input, etc.
    Callers (routes.py) turn this into a 400, never a 500."""


def _set_status(claim: ListingClaim, status: str, sync_listing: bool = True):
    claim.status = status
    if sync_listing and claim.listing is not None:
        claim.listing.claim_status = status
    db.session.commit()


class ListingClaimService:

    @staticmethod
    def search_listings(source: str | None = None, location_text: str | None = None,
                         page: int = 1, per_page: int = 20):
        """Public search — only over listings still open to claim. Returns
        disambiguation info only: source, coarse location, discovered_at.
        Never the raw source_url (see SourceListing.to_dict's default)."""
        from backend.shared.utils.pagination import paginate_query

        query = SourceListing.query.filter(
            SourceListing.claim_status.in_(CLAIMABLE_LISTING_STATUSES)
        )
        if source:
            query = query.filter_by(source=source)
        if location_text:
            query = query.filter(SourceListing.location_text.ilike(f'%{location_text}%'))
        query = query.order_by(SourceListing.discovered_at.desc())

        items, total, current_page, last_page, per_page = paginate_query(query, page, per_page)
        return [i.to_dict() for i in items], total, current_page, last_page, per_page

    @staticmethod
    def start_claim(source_listing_id: str, claimant_phone: str) -> ListingClaim:
        listing = db.session.get(SourceListing, source_listing_id)
        if listing is None:
            raise ClaimError('Listing not found.')

        existing = ListingClaim.query.filter_by(source_listing_id=source_listing_id).filter(
            ListingClaim.status.in_(ACTIVE_CLAIM_STATUSES)
        ).first()
        if existing:
            # Idempotent: don't start a second concurrent claim on the same
            # listing — hand back the one already in progress. This isn't
            # necessarily the same phone number; that's fine, the first
            # claimant to actually pass verification wins, this just stops
            # duplicate claim rows piling up per listing.
            return existing

        if listing.claim_status not in CLAIMABLE_LISTING_STATUSES:
            raise ClaimError(f"Listing is not claimable (status={listing.claim_status}).")

        claim = ListingClaim(
            source_listing_id=source_listing_id,
            claimant_phone=claimant_phone,
            status='claim_requested',
        )
        db.session.add(claim)
        listing.claim_status = 'claim_requested'
        db.session.commit()
        logger.info(f"[Listings] claim started claim_id={claim.id} listing_id={source_listing_id}")
        return claim

    @staticmethod
    def request_otp(claim_id: str) -> None:
        from backend.domains.identity.service import create_otp

        claim = db.session.get(ListingClaim, claim_id)
        if claim is None:
            raise ClaimError('Claim not found.')
        if not claim.claimant_phone:
            raise ClaimError('Claim has no phone number to verify.')
        if claim.status not in ('claim_requested', 'verification_pending'):
            raise ClaimError(f"Cannot request OTP in status={claim.status}.")

        create_otp(claim.claimant_phone, purpose='listing_claim')
        _set_status(claim, 'verification_pending')
        logger.info(f"[Listings] OTP requested claim_id={claim_id}")

    @staticmethod
    def verify_otp_step(claim_id: str, code: str) -> tuple[bool, str]:
        from backend.domains.identity.service import verify_otp

        claim = db.session.get(ListingClaim, claim_id)
        if claim is None:
            raise ClaimError('Claim not found.')

        ok, message = verify_otp(claim.claimant_phone, code, purpose='listing_claim')
        event = ClaimVerificationEvent(
            claim_id=claim.id, method='otp',
            result='passed' if ok else 'failed',
            notes=None if ok else message,
        )
        db.session.add(event)
        db.session.commit()

        if ok:
            logger.info(f"[Listings] OTP verified claim_id={claim_id}")
            ListingClaimService._try_authorize(claim)
        return ok, message

    @staticmethod
    def submit_liveness_capture(claim_id: str, file) -> ListingClaim:
        from backend.shared.storage import save_upload

        claim = db.session.get(ListingClaim, claim_id)
        if claim is None:
            raise ClaimError('Claim not found.')
        if claim.status not in ('claim_requested', 'verification_pending'):
            raise ClaimError(f"Cannot submit a liveness capture in status={claim.status}.")

        path = save_upload(file, folder=f'listing_claims/{claim.id}')
        if not path:
            raise ClaimError('Could not store the uploaded image — check file type.')

        claim.liveness_capture_path = path
        if claim.status == 'claim_requested':
            _set_status(claim, 'verification_pending')
        else:
            db.session.commit()
        logger.info(f"[Listings] liveness capture submitted claim_id={claim_id}")
        return claim

    @staticmethod
    def admin_review_liveness(claim_id: str, admin_account, passed: bool, notes: str | None = None) -> ListingClaim:
        """v1: a human admin visually compares the liveness capture against
        the claimed listing's photos and attests to the result. This is
        deliberately still just ONE of the two required events — it does not
        authorize the claim by itself, and no admin action here can skip the
        otp factor. See plan §5.3 for why this is a v1 simplification, not a
        loophole: the destination is 'authorized', which is unreachable
        through this method alone."""
        claim = db.session.get(ListingClaim, claim_id)
        if claim is None:
            raise ClaimError('Claim not found.')
        if not claim.liveness_capture_path:
            raise ClaimError('No liveness capture has been submitted for this claim yet.')

        event = ClaimVerificationEvent(
            claim_id=claim.id, method='liveness_match',
            result='passed' if passed else 'failed',
            notes=notes,
        )
        db.session.add(event)
        claim.liveness_reviewed_by = admin_account.id
        db.session.commit()

        logger.info(f"[Listings] liveness reviewed claim_id={claim_id} passed={passed} by={admin_account.id}")
        if passed:
            ListingClaimService._try_authorize(claim)
        return claim

    @staticmethod
    def _try_authorize(claim: ListingClaim) -> bool:
        """The ONLY place authorized_at/status='authorized' gets set. Requires
        an 'otp' passed event AND a 'liveness_match' passed event to exist —
        not just the one that just happened, so it's safe to call after
        either factor completes, in either order."""
        events = ClaimVerificationEvent.query.filter_by(claim_id=claim.id, result='passed').all()
        methods_passed = {e.method for e in events}
        if not {'otp', 'liveness_match'}.issubset(methods_passed):
            return False

        liveness_event = next(e for e in events if e.method == 'liveness_match')
        claim.authorized_at = datetime.utcnow()
        claim.authorization_event_id = liveness_event.id
        _set_status(claim, 'authorized')
        logger.info(f"[Listings] claim authorized claim_id={claim.id}")
        return True

    @staticmethod
    def admin_transition(claim_id: str, new_status: str, admin_account, reason: str | None = None) -> ListingClaim:
        """The only entry point admin routes may call to move a claim's
        status. Enforces ADMIN_ALLOWED_TRANSITIONS — 'authorized' is not a
        reachable destination through this method under any input."""
        claim = db.session.get(ListingClaim, claim_id)
        if claim is None:
            raise ClaimError('Claim not found.')

        if (claim.status, new_status) not in ADMIN_ALLOWED_TRANSITIONS:
            raise ClaimError(f"Admin transition {claim.status} -> {new_status} is not permitted.")

        if new_status == 'rejected':
            claim.rejected_reason = reason or 'Rejected by admin.'
        _set_status(claim, new_status)
        logger.info(f"[Listings] admin transition claim_id={claim_id} -> {new_status} by={admin_account.id}")
        return claim

    @staticmethod
    def list_claims(status: str | None = None, page: int = 1, per_page: int = 20):
        from backend.shared.utils.pagination import paginate_query

        query = ListingClaim.query
        if status:
            query = query.filter_by(status=status)
        query = query.order_by(ListingClaim.created_at.desc())

        items, total, current_page, last_page, per_page = paginate_query(query, page, per_page)
        return [c.to_dict() for c in items], total, current_page, last_page, per_page
