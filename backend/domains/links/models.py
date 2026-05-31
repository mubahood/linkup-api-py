"""
Links domain model: Link (professional connections)
"""
import uuid
from datetime import datetime
from backend.models import db


class Link(db.Model):
    __tablename__ = 'lu_links'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    requester_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    addressee_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    status = db.Column(db.String(20), default='requested')
    note = db.Column(db.String(1000), nullable=True)
    strength_score = db.Column(db.Numeric(5, 4), default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    requester = db.relationship('Account', foreign_keys=[requester_id], lazy='joined')
    addressee = db.relationship('Account', foreign_keys=[addressee_id], lazy='joined')

    def to_dict(self, viewer_id=None):
        return {
            'id': self.id,
            'requester_id': self.requester_id,
            'addressee_id': self.addressee_id,
            'status': self.status,
            'note': self.note,
            'strength_score': float(self.strength_score) if self.strength_score else 0.0,
            'requester': self.requester.to_dict() if self.requester else None,
            'addressee': self.addressee.to_dict() if self.addressee else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
