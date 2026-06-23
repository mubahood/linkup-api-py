"""Behavioral event model (T-API-053)."""
import uuid
from datetime import datetime
from backend.models import db


class BehavioralEvent(db.Model):
    __tablename__ = 'lu_behavioral_events'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), nullable=True)
    verb = db.Column(db.String(40), nullable=False)        # e.g. spark.up, profile.view
    object_type = db.Column(db.String(40), nullable=True)  # e.g. account, job, post
    object_id = db.Column(db.String(36), nullable=True)
    context = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'verb': self.verb,
            'object_type': self.object_type,
            'object_id': self.object_id,
            'context': self.context,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
