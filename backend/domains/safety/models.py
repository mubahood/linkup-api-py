"""
Safety domain models: Report, Block, SafetyContact, DateCheckin
"""
import uuid
from datetime import datetime
from backend.models import db


class Report(db.Model):
    __tablename__ = 'lu_reports'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    reporter_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    target_account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    target_content_type = db.Column(db.String(100), nullable=True)
    target_content_id = db.Column(db.String(36), nullable=True)
    reason = db.Column(db.String(50), default='other')
    detail = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'reporter_id': self.reporter_id,
            'target_account_id': self.target_account_id,
            'target_content_type': self.target_content_type,
            'target_content_id': self.target_content_id,
            'reason': self.reason,
            'detail': self.detail,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Block(db.Model):
    __tablename__ = 'lu_blocks'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    blocker_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    blocked_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    blocked = db.relationship('Account', foreign_keys=[blocked_id], lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'blocker_id': self.blocker_id,
            'blocked_id': self.blocked_id,
            'blocked_account': self.blocked.to_dict() if self.blocked else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SafetyContact(db.Model):
    """A trusted contact the user can share their location with or ping in an emergency."""
    __tablename__ = 'lu_safety_contacts'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    linked_account_id = db.Column(db.String(36), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'name': self.name,
            'phone': self.phone,
            'linked_account_id': self.linked_account_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class PanicAlert(db.Model):
    """Persistent log of every SOS/panic trigger — POST /v1/safety/panic used to fire
    notifications and vanish with no queryable record. This is the admin-visible trail."""
    __tablename__ = 'lu_panic_alerts'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    checkin_id = db.Column(db.String(36), nullable=True)
    location_text = db.Column(db.String(500), nullable=True)
    contacts_notified = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='open')  # open | acknowledged | resolved
    resolved_by = db.Column(db.String(36), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolution_note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    account = db.relationship('Account', foreign_keys=[account_id], lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'account': {'id': self.account.id, 'display_name': self.account.display_name,
                        'handle': self.account.handle, 'phone': self.account.phone,
                        'avatar': self.account.avatar} if self.account else None,
            'checkin_id': self.checkin_id,
            'location_text': self.location_text,
            'contacts_notified': self.contacts_notified,
            'status': self.status,
            'resolved_by': self.resolved_by,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolution_note': self.resolution_note,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class DateCheckin(db.Model):
    """Scheduled date safety check-in. User tells the app 'I have a date at 8pm — check on me at 9pm'."""
    __tablename__ = 'lu_date_checkins'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    match_id = db.Column(db.String(36), nullable=True)
    location_text = db.Column(db.String(500), nullable=True)
    check_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='active')  # active|checked_in|missed|cancelled
    panic_sent = db.Column(db.SmallInteger, default=0)
    note = db.Column(db.Text, nullable=True)
    share_token = db.Column(db.String(64), nullable=True, unique=True)
    share_expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'match_id': self.match_id,
            'location_text': self.location_text,
            'check_time': self.check_time.isoformat() if self.check_time else None,
            'status': self.status,
            'panic_sent': bool(self.panic_sent),
            'note': self.note,
            'share_token': self.share_token,
            'share_expires_at': self.share_expires_at.isoformat() if self.share_expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
