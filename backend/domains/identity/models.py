"""
Identity domain models:
  Account, AccountDevice, OtpRequest, RefreshToken, Verification
"""
import json
import uuid
from datetime import datetime
from backend.models import db


class Account(db.Model):
    __tablename__ = 'lu_accounts'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    handle = db.Column(db.String(100), unique=True, nullable=False)
    display_name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(30), unique=True, nullable=True)
    email = db.Column(db.String(300), unique=True, nullable=True)
    phone_verified = db.Column(db.SmallInteger, default=0)
    email_verified = db.Column(db.SmallInteger, default=0)
    password_hash = db.Column(db.String(500), nullable=True)
    kyc_level = db.Column(db.SmallInteger, default=0)
    # Which app this account signed up through ('linkup' | 'abanoonya') — set
    # once at creation from the X-App header, never changed after. Used to
    # keep professional-mode content (jobs, mentorship, links, endorsements)
    # from ever reaching an Abanoonya Pro account, even via a cross-app social
    # action (e.g. a LinkUp user sending a job referral to this account).
    app_id = db.Column(db.String(20), nullable=False, default='linkup')
    modes_enabled = db.Column(db.JSON, nullable=False, default=lambda: {"professional": True, "sparks": False})
    account_status = db.Column(db.String(20), default='active')
    reputation_score = db.Column(db.Numeric(5, 2), default=0.00)
    avatar = db.Column(db.String(500), nullable=True)
    cover_photo = db.Column(db.String(500), nullable=True)
    location_id = db.Column(db.String(36), db.ForeignKey('lu_locations.id', ondelete='SET NULL'), nullable=True)
    is_admin = db.Column(db.SmallInteger, default=0)
    is_premium = db.Column(db.SmallInteger, default=0)
    # Denormalized subscription entitlement — kept in sync by
    # subscriptions.service so a per-request gate check never has to join
    # lu_subscriptions. Source of truth for is_premium once a plan is set.
    subscription_plan_id = db.Column(db.String(36), nullable=True)
    subscription_expires_at = db.Column(db.DateTime, nullable=True)
    # Gamification: real consecutive-day streak (touched on genuine
    # engagement) and a one-shot first-match milestone bonus.
    streak_days = db.Column(db.Integer, default=0)
    streak_updated_at = db.Column(db.DateTime, nullable=True)
    first_match_bonus_available = db.Column(db.SmallInteger, default=0)
    notification_prefs = db.Column(db.JSON, nullable=True)
    last_lat = db.Column(db.Numeric(10, 7), nullable=True)
    last_lng = db.Column(db.Numeric(10, 7), nullable=True)
    location_updated_at = db.Column(db.DateTime, nullable=True)  # when GPS was last recorded
    last_seen_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def set_password(self, password: str):
        import bcrypt
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt()
        ).decode('utf-8')

    def check_password(self, password: str) -> bool:
        import bcrypt
        if not self.password_hash:
            return False
        return bcrypt.checkpw(
            password.encode('utf-8'),
            self.password_hash.encode('utf-8')
        )

    @property
    def modes(self):
        """Safe accessor for modes_enabled — always a dict (see T-API-041)."""
        from backend.shared.json_safe import as_obj
        return as_obj(self.modes_enabled)

    @property
    def notif_prefs(self):
        """Safe accessor for notification_prefs — always a dict (see T-API-041)."""
        from backend.shared.json_safe import as_obj
        return as_obj(self.notification_prefs)

    def is_online(self, threshold_minutes: int = 10) -> bool:
        """True if last_seen_at is within threshold_minutes of now."""
        if not self.last_seen_at:
            return False
        from datetime import datetime
        delta = datetime.utcnow() - self.last_seen_at
        return delta.total_seconds() < threshold_minutes * 60

    def needs_location_update(self, max_age_days: int = 7) -> bool:
        """True if GPS was never recorded or is older than max_age_days.
        Drives the 'refresh your location weekly' prompt for distance matching."""
        if not self.location_updated_at:
            return True
        from datetime import datetime
        return (datetime.utcnow() - self.location_updated_at).days >= max_age_days

    def to_dict(self, include_private: bool = False):
        """Safe by default: phone, email, verification flags, kyc_level, and
        precise GPS (last_lat/last_lng) are withheld unless the caller is
        genuinely the account owner or an authorised admin viewing this
        exact account — pass include_private=True only for those two cases.
        Every other caller (search results, chat participants, post/comment
        authors, link/connection lists, event attendees, etc.) must get the
        safe default; this was previously unconditional and leaked all of
        the above to any authenticated viewer regardless of relationship."""
        d = {
            'id': self.id,
            'handle': self.handle,
            'display_name': self.display_name,
            'app_id': self.app_id,
            'is_admin': bool(self.is_admin),
            'is_premium': bool(self.is_premium),
            'subscription_plan_id': self.subscription_plan_id,
            'subscription_expires_at':
                self.subscription_expires_at.isoformat() if self.subscription_expires_at else None,
            'modes_enabled': self.modes,
            'account_status': self.account_status,
            'reputation_score': float(self.reputation_score) if self.reputation_score else 0.0,
            'avatar': self.avatar,
            'cover_photo': self.cover_photo,
            'location_id': self.location_id,
            'location_updated_at':
                self.location_updated_at.isoformat() if self.location_updated_at else None,
            'needs_location_update': self.needs_location_update(),
            'last_seen_at': self.last_seen_at.isoformat() if self.last_seen_at else None,
            'is_online': self.is_online(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_private:
            d.update({
                'phone': self.phone,
                'email': self.email,
                'phone_verified': bool(self.phone_verified),
                'email_verified': bool(self.email_verified),
                'kyc_level': self.kyc_level,
                'last_lat': float(self.last_lat) if self.last_lat is not None else None,
                'last_lng': float(self.last_lng) if self.last_lng is not None else None,
            })
        return d


class AccountDevice(db.Model):
    __tablename__ = 'lu_account_devices'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    device_token = db.Column(db.String(500), nullable=True)
    platform = db.Column(db.String(20), default='android')
    onesignal_player_id = db.Column(db.String(200), nullable=True)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class OtpRequest(db.Model):
    __tablename__ = 'lu_otp_requests'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    phone = db.Column(db.String(300), nullable=False)  # stores email or phone as identifier
    code_hash = db.Column(db.String(500), nullable=False)
    purpose = db.Column(db.String(20), default='login')
    expires_at = db.Column(db.DateTime, nullable=False)
    verified_at = db.Column(db.DateTime, nullable=True)
    attempts = db.Column(db.SmallInteger, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RefreshToken(db.Model):
    __tablename__ = 'lu_refresh_tokens'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    token_hash = db.Column(db.String(500), nullable=False)
    device_id = db.Column(db.String(36), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Verification(db.Model):
    """KYC submission — one row per attempt (a rejected submission and its
    later resubmission are two separate rows, so history is never lost).
    id_photo_url/selfie_url are real columns (migration 0046), not buried in
    the generic `metadata` JSON blob, mirroring how listings/models.py's
    ListingClaim stores its liveness_capture_path — an admin reviewing this
    needs an actual photo to look at, not a JSON string."""
    __tablename__ = 'lu_verifications'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    type = db.Column(db.String(20), default='national_id')
    status = db.Column(db.String(20), default='pending')
    metadata_json = db.Column('metadata', db.JSON, nullable=True)
    id_photo_url = db.Column(db.String(500), nullable=True)
    selfie_url = db.Column(db.String(500), nullable=True)
    rejection_reason = db.Column(db.String(500), nullable=True)
    reviewed_by = db.Column(db.String(36), nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'type': self.type,
            'status': self.status,
            'national_id': (self.metadata_json or {}).get('national_id') if self.metadata_json else None,
            'id_photo_url': self.id_photo_url,
            'selfie_url': self.selfie_url,
            'rejection_reason': self.rejection_reason,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
