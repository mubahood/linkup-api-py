"""Job referral model."""
import uuid
from datetime import datetime
from backend.models import db


class JobReferral(db.Model):
    __tablename__ = 'lu_job_referrals'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = db.Column(db.String(36), db.ForeignKey('lu_jobs.id', ondelete='CASCADE'), nullable=False)
    requester_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    referrer_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    message = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending|accepted|declined|referred
    responded_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    requester = db.relationship('Account', foreign_keys=[requester_id], lazy='joined')
    referrer = db.relationship('Account', foreign_keys=[referrer_id], lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'job_id': self.job_id,
            'requester_id': self.requester_id,
            'referrer_id': self.referrer_id,
            'message': self.message,
            'status': self.status,
            'responded_at': self.responded_at.isoformat() if self.responded_at else None,
            'requester': self.requester.to_dict() if self.requester else None,
            'referrer': self.referrer.to_dict() if self.referrer else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
