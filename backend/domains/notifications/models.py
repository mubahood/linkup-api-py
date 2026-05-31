"""
Notifications domain model: Notification
"""
import uuid
from datetime import datetime
from backend.models import db


class Notification(db.Model):
    __tablename__ = 'lu_notifications'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    type = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    body = db.Column(db.Text, nullable=True)
    data = db.Column(db.JSON, nullable=True)
    is_read = db.Column(db.SmallInteger, default=0)
    action_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'type': self.type,
            'title': self.title,
            'body': self.body,
            'data': self.data,
            'is_read': bool(self.is_read),
            'action_url': self.action_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
