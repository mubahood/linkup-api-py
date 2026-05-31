"""
Safety domain models: Report, Block
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
