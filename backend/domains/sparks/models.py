"""
Sparks domain models: Spark, Match
"""
import uuid
from datetime import datetime
from backend.models import db


class Spark(db.Model):
    __tablename__ = 'lu_sparks'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    target_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    action = db.Column(db.String(20), nullable=False)  # spark_up, pass, standout, undo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    actor = db.relationship('Account', foreign_keys=[actor_id], lazy='joined')
    target = db.relationship('Account', foreign_keys=[target_id], lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'actor_id': self.actor_id,
            'target_id': self.target_id,
            'action': self.action,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Match(db.Model):
    __tablename__ = 'lu_matches'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_a_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    account_b_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    spark_a_id = db.Column(db.String(36), nullable=True)
    spark_b_id = db.Column(db.String(36), nullable=True)
    thread_id = db.Column(db.String(36), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    account_a = db.relationship('Account', foreign_keys=[account_a_id], lazy='joined')
    account_b = db.relationship('Account', foreign_keys=[account_b_id], lazy='joined')

    def to_dict(self, viewer_id=None):
        other = self.account_b if viewer_id == self.account_a_id else self.account_a
        return {
            'id': self.id,
            'account_a_id': self.account_a_id,
            'account_b_id': self.account_b_id,
            'thread_id': self.thread_id,
            'other_account': other.to_dict() if other else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
