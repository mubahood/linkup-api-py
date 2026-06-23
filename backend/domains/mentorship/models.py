"""Mentorship domain models."""
import uuid
from datetime import datetime
from backend.models import db


class MentorProfile(db.Model):
    """A professional offering mentorship. One per account."""
    __tablename__ = 'lu_mentor_profiles'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'),
                           nullable=False, unique=True)
    headline = db.Column(db.String(300), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    skills = db.Column(db.JSON, nullable=True)       # list of skill tag_ids or free-text strings
    industries = db.Column(db.JSON, nullable=True)   # list of industry strings
    mentorship_mode = db.Column(db.String(20), default='both')   # online|in_person|both
    session_duration = db.Column(db.SmallInteger, default=60)    # minutes per session
    capacity = db.Column(db.SmallInteger, default=3)             # max active mentees
    is_open = db.Column(db.SmallInteger, default=1)
    session_count = db.Column(db.SmallInteger, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    account = db.relationship('Account', foreign_keys=[account_id], lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'account': self.account.to_dict() if self.account else None,
            'headline': self.headline,
            'bio': self.bio,
            'skills': self.skills or [],
            'industries': self.industries or [],
            'mentorship_mode': self.mentorship_mode,
            'session_duration': self.session_duration,
            'capacity': self.capacity,
            'is_open': bool(self.is_open),
            'session_count': self.session_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class MentorshipRequest(db.Model):
    """A mentee's request to a mentor."""
    __tablename__ = 'lu_mentorship_requests'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mentee_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'),
                          nullable=False)
    mentor_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'),
                          nullable=False)
    message = db.Column(db.Text, nullable=True)
    goals = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending')   # pending|accepted|declined|completed|withdrawn
    responded_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    mentee = db.relationship('Account', foreign_keys=[mentee_id], lazy='joined')
    mentor = db.relationship('Account', foreign_keys=[mentor_id], lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'mentee_id': self.mentee_id,
            'mentor_id': self.mentor_id,
            'mentee': self.mentee.to_dict() if self.mentee else None,
            'mentor': self.mentor.to_dict() if self.mentor else None,
            'message': self.message,
            'goals': self.goals,
            'status': self.status,
            'responded_at': self.responded_at.isoformat() if self.responded_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
