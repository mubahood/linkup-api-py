"""
Chat domain models: Thread, ThreadParticipant, Message
"""
import uuid
from datetime import datetime
from backend.models import db


class Thread(db.Model):
    __tablename__ = 'lu_threads'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    type = db.Column(db.String(20), default='direct')
    mode = db.Column(db.String(20), default='professional')
    created_by = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    hub_id = db.Column(db.String(36), db.ForeignKey('lu_hubs.id', ondelete='SET NULL'), nullable=True)
    title = db.Column(db.String(300), nullable=True)
    last_message_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    participants = db.relationship('ThreadParticipant', backref='thread', lazy='dynamic')

    def to_dict(self, viewer_id=None, last_message=None, unread_count=0):
        return {
            'id': self.id,
            'type': self.type,
            'mode': self.mode,
            'created_by': self.created_by,
            'hub_id': self.hub_id,
            'title': self.title,
            'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None,
            'last_message': last_message,
            'unread_count': unread_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ThreadParticipant(db.Model):
    __tablename__ = 'lu_thread_participants'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    thread_id = db.Column(db.String(36), db.ForeignKey('lu_threads.id', ondelete='CASCADE'), nullable=False)
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_read_at = db.Column(db.DateTime, nullable=True)

    account = db.relationship('Account', foreign_keys=[account_id], lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'thread_id': self.thread_id,
            'account_id': self.account_id,
            'account': self.account.to_dict() if self.account else None,
            'joined_at': self.joined_at.isoformat() if self.joined_at else None,
            'last_read_at': self.last_read_at.isoformat() if self.last_read_at else None,
        }


class MessageReaction(db.Model):
    __tablename__ = 'lu_message_reactions'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = db.Column(db.String(36), db.ForeignKey('lu_messages.id', ondelete='CASCADE'), nullable=False)
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    emoji = db.Column(db.String(10), nullable=False, default='👍')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    account = db.relationship('Account', foreign_keys=[account_id], lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'message_id': self.message_id,
            'account_id': self.account_id,
            'emoji': self.emoji,
            'account': self.account.to_dict() if self.account else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Message(db.Model):
    __tablename__ = 'lu_messages'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    thread_id = db.Column(db.String(36), db.ForeignKey('lu_threads.id', ondelete='CASCADE'), nullable=False)
    sender_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    body = db.Column(db.Text, nullable=True)
    type = db.Column(db.String(20), default='text')
    media = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(20), default='sent')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)

    sender = db.relationship('Account', foreign_keys=[sender_id], lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'thread_id': self.thread_id,
            'sender_id': self.sender_id,
            'body': self.body,
            'type': self.type,
            'media': self.media,
            'status': self.status,
            'sender': self.sender.to_dict() if self.sender else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
