"""
Events domain models: Event, EventRSVP
"""
import uuid
from datetime import datetime
from backend.models import db


class Event(db.Model):
    __tablename__ = 'lu_events'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id = db.Column(db.String(36), db.ForeignKey('lu_orgs.id', ondelete='SET NULL'), nullable=True)
    created_by = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    event_type = db.Column(db.String(30), default='networking')
    start_at = db.Column(db.DateTime, nullable=False)
    end_at = db.Column(db.DateTime, nullable=True)
    location_text = db.Column(db.String(500), nullable=True)
    is_online = db.Column(db.SmallInteger, default=0)
    link = db.Column(db.String(500), nullable=True)
    cover_image = db.Column(db.String(500), nullable=True)
    max_attendees = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship('Account', foreign_keys=[created_by], lazy='joined')

    def to_dict(self, my_rsvp=None, attendee_count=0):
        return {
            'id': self.id,
            'org_id': self.org_id,
            'created_by': self.created_by,
            'creator': self.creator.to_dict() if self.creator else None,
            'title': self.title,
            'description': self.description,
            'event_type': self.event_type,
            'start_at': self.start_at.isoformat() if self.start_at else None,
            'end_at': self.end_at.isoformat() if self.end_at else None,
            'location_text': self.location_text,
            'is_online': bool(self.is_online),
            'link': self.link,
            'cover_image': self.cover_image,
            'max_attendees': self.max_attendees,
            'attendee_count': attendee_count,
            'my_rsvp': my_rsvp.status if my_rsvp else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class EventRSVP(db.Model):
    __tablename__ = 'lu_event_rsvps'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = db.Column(db.String(36), db.ForeignKey('lu_events.id', ondelete='CASCADE'), nullable=False)
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    status = db.Column(db.String(20), default='going')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'event_id': self.event_id,
            'account_id': self.account_id,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
