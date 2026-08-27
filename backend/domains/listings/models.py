"""
Listings domain models: SourceListing, SourceCrawl.

Discovery-only stage of the claim-and-verify profile importer — see
PROFILE_CLAIM_IMPORTER_PLAN.md for the full pipeline design. SourceListing
must never gain columns for photos, bio, or contact details: those only
exist after a claim is authorized (Phase 5+), in tables that don't exist yet.
"""
import uuid
from datetime import datetime
from backend.models import db


class SourceListing(db.Model):
    __tablename__ = 'lu_source_listings'

    # Full claim-status lifecycle (see plan §2.2). Stored as VARCHAR, not a
    # MySQL ENUM, so adding a state later is a code change, not a migration —
    # matches the rest of this codebase's status-column convention (e.g.
    # PanicAlert.status, DateCheckin.status).
    VALID_CLAIM_STATUSES = {
        'discovered', 'claim_available', 'claim_requested', 'verification_pending',
        'verified', 'authorized', 'importing', 'imported', 'user_review',
        'published', 'rejected', 'removal_requested', 'removed', 'suppressed',
    }

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source = db.Column(db.String(50), nullable=False)
    external_id = db.Column(db.String(200), nullable=False)
    source_url = db.Column(db.String(1000), nullable=False)
    canonical_url = db.Column(db.String(1000), nullable=False)
    location_text = db.Column(db.String(200), nullable=True)
    discovered_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_checked_at = db.Column(db.DateTime, nullable=True)
    claim_status = db.Column(db.String(30), nullable=False, default='discovered')
    parser_version = db.Column(db.String(50), nullable=True)

    __table_args__ = (
        db.UniqueConstraint('source', 'external_id', name='uq_source_external'),
    )

    def to_dict(self, include_source_url: bool = False):
        """`source_url` is admin/internal-only by default — a future public
        claim-search endpoint (Phase 4) must not leak the raw source link
        past what's needed to disambiguate a listing."""
        data = {
            'id': self.id,
            'source': self.source,
            'external_id': self.external_id,
            'canonical_url': self.canonical_url,
            'location_text': self.location_text,
            'discovered_at': self.discovered_at.isoformat() if self.discovered_at else None,
            'last_checked_at': self.last_checked_at.isoformat() if self.last_checked_at else None,
            'claim_status': self.claim_status,
            'parser_version': self.parser_version,
        }
        if include_source_url:
            data['source_url'] = self.source_url
        return data


class ListingClaim(db.Model):
    __tablename__ = 'lu_listing_claims'

    # No status here is admin-settable in isolation to 'authorized' — that
    # transition is system_only, enforced in ListingClaimService, not by a
    # constraint on this set. See plan §6.
    VALID_STATUSES = {
        'claim_requested', 'verification_pending', 'verified', 'authorized',
        'importing', 'imported', 'user_review', 'published', 'rejected',
        'removal_requested', 'removed',
    }

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_listing_id = db.Column(
        db.String(36), db.ForeignKey('lu_source_listings.id', ondelete='CASCADE'), nullable=False
    )
    claimant_phone = db.Column(db.String(30), nullable=True)
    claimant_account_id = db.Column(db.String(36), nullable=True)
    status = db.Column(db.String(30), nullable=False, default='claim_requested')
    liveness_capture_path = db.Column(db.String(500), nullable=True)
    liveness_reviewed_by = db.Column(db.String(36), nullable=True)
    authorized_at = db.Column(db.DateTime, nullable=True)
    authorization_event_id = db.Column(db.String(36), nullable=True)
    rejected_reason = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    listing = db.relationship('SourceListing', foreign_keys=[source_listing_id], lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'source_listing_id': self.source_listing_id,
            'status': self.status,
            'liveness_capture_path': self.liveness_capture_path,
            'liveness_reviewed_by': self.liveness_reviewed_by,
            'authorized_at': self.authorized_at.isoformat() if self.authorized_at else None,
            'rejected_reason': self.rejected_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class ClaimVerificationEvent(db.Model):
    __tablename__ = 'lu_claim_verification_events'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    claim_id = db.Column(db.String(36), db.ForeignKey('lu_listing_claims.id', ondelete='CASCADE'), nullable=False)
    method = db.Column(db.String(30), nullable=False)  # 'otp' | 'liveness_match'
    result = db.Column(db.String(20), nullable=False)  # 'passed' | 'failed'
    confidence = db.Column(db.Numeric(5, 2), nullable=True)
    notes = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'claim_id': self.claim_id,
            'method': self.method,
            'result': self.result,
            'confidence': float(self.confidence) if self.confidence is not None else None,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SourceCrawl(db.Model):
    __tablename__ = 'lu_source_crawls'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source = db.Column(db.String(50), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    pages_visited = db.Column(db.Integer, nullable=False, default=0)
    listings_found = db.Column(db.Integer, nullable=False, default=0)
    listings_new = db.Column(db.Integer, nullable=False, default=0)
    errors = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default='running')  # running|completed|failed|paused_health
    error_detail = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'source': self.source,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'pages_visited': self.pages_visited,
            'listings_found': self.listings_found,
            'listings_new': self.listings_new,
            'errors': self.errors,
            'status': self.status,
            'error_detail': self.error_detail,
        }
