"""
Jobs domain models: Job, Application, SavedJob
"""
import uuid
from datetime import datetime
from backend.models import db


class Job(db.Model):
    __tablename__ = 'lu_jobs'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id = db.Column(db.String(36), db.ForeignKey('lu_orgs.id', ondelete='SET NULL'), nullable=True)
    org_name = db.Column(db.String(300), nullable=True)
    posted_by = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    location_id = db.Column(db.String(36), db.ForeignKey('lu_locations.id', ondelete='SET NULL'), nullable=True)
    location_text = db.Column(db.String(300), nullable=True)
    employment_type = db.Column(db.String(30), default='full_time')
    seniority = db.Column(db.String(30), default='entry')
    salary_min = db.Column(db.Numeric(12, 2), nullable=True)
    salary_max = db.Column(db.Numeric(12, 2), nullable=True)
    currency = db.Column(db.String(10), default='UGX')
    skills = db.Column(db.JSON, nullable=True)
    is_open = db.Column(db.SmallInteger, default=1)
    referral_open = db.Column(db.SmallInteger, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)

    poster = db.relationship('Account', foreign_keys=[posted_by], lazy='joined')

    def to_dict(self, is_saved=False, application=None):
        return {
            'id': self.id,
            'org_id': self.org_id,
            'org_name': self.org_name,
            'posted_by': self.posted_by,
            'poster': self.poster.to_dict() if self.poster else None,
            'title': self.title,
            'description': self.description,
            'location_id': self.location_id,
            'location_text': self.location_text,
            'employment_type': self.employment_type,
            'seniority': self.seniority,
            'salary_min': float(self.salary_min) if self.salary_min else None,
            'salary_max': float(self.salary_max) if self.salary_max else None,
            'currency': self.currency,
            'skills': self.skills,
            'is_open': bool(self.is_open),
            'referral_open': bool(self.referral_open),
            'is_saved': is_saved,
            'my_application': application.to_dict() if application else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
        }


class Application(db.Model):
    __tablename__ = 'lu_applications'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = db.Column(db.String(36), db.ForeignKey('lu_jobs.id', ondelete='CASCADE'), nullable=False)
    applicant_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    cover_note = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='applied')
    referred_by = db.Column(db.String(36), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    applicant = db.relationship('Account', foreign_keys=[applicant_id], lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'job_id': self.job_id,
            'applicant_id': self.applicant_id,
            'cover_note': self.cover_note,
            'status': self.status,
            'referred_by': self.referred_by,
            'applicant': self.applicant.to_dict() if self.applicant else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SavedJob(db.Model):
    __tablename__ = 'lu_saved_jobs'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = db.Column(db.String(36), db.ForeignKey('lu_jobs.id', ondelete='CASCADE'), nullable=False)
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
