"""
Profile domain models:
  ProfessionalProfile, DatingProfile, Education, Experience, Certification
"""
import uuid
from datetime import datetime
from backend.models import db


class ProfessionalProfile(db.Model):
    __tablename__ = 'lu_professional_profiles'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False, unique=True)
    headline = db.Column(db.String(500), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    seniority = db.Column(db.String(30), default='entry')
    current_role = db.Column(db.String(300), nullable=True)
    current_org_id = db.Column(db.String(36), db.ForeignKey('lu_orgs.id', ondelete='SET NULL'), nullable=True)
    visibility_mode = db.Column(db.String(30), default='public')
    open_to = db.Column(db.JSON, nullable=True)
    location_id = db.Column(db.String(36), db.ForeignKey('lu_locations.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'headline': self.headline,
            'bio': self.bio,
            'seniority': self.seniority,
            'current_role': self.current_role,
            'current_org_id': self.current_org_id,
            'visibility_mode': self.visibility_mode,
            'open_to': self.open_to,
            'location_id': self.location_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class DatingProfile(db.Model):
    __tablename__ = 'lu_dating_profiles'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False, unique=True)
    display_name = db.Column(db.String(200), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    age_min = db.Column(db.SmallInteger, default=18)
    age_max = db.Column(db.SmallInteger, default=40)
    intent = db.Column(db.String(30), default='open')
    lifestyle = db.Column(db.JSON, nullable=True)
    prompts = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'display_name': self.display_name,
            'bio': self.bio,
            'age_min': self.age_min,
            'age_max': self.age_max,
            'intent': self.intent,
            'lifestyle': self.lifestyle,
            'prompts': self.prompts,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Education(db.Model):
    __tablename__ = 'lu_education'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    institution_id = db.Column(db.String(36), db.ForeignKey('lu_institutions.id', ondelete='SET NULL'), nullable=True)
    institution_name = db.Column(db.String(300), nullable=True)
    degree = db.Column(db.String(200), nullable=True)
    field = db.Column(db.String(200), nullable=True)
    start_year = db.Column(db.SmallInteger, nullable=True)
    end_year = db.Column(db.SmallInteger, nullable=True)
    verified = db.Column(db.SmallInteger, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'institution_id': self.institution_id,
            'institution_name': self.institution_name,
            'degree': self.degree,
            'field': self.field,
            'start_year': self.start_year,
            'end_year': self.end_year,
            'verified': bool(self.verified),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Experience(db.Model):
    __tablename__ = 'lu_experience'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    org_id = db.Column(db.String(36), db.ForeignKey('lu_orgs.id', ondelete='SET NULL'), nullable=True)
    org_name = db.Column(db.String(300), nullable=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    is_current = db.Column(db.SmallInteger, default=0)
    verified = db.Column(db.SmallInteger, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'org_id': self.org_id,
            'org_name': self.org_name,
            'title': self.title,
            'description': self.description,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'is_current': bool(self.is_current),
            'verified': bool(self.verified),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Certification(db.Model):
    __tablename__ = 'lu_certifications'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(300), nullable=False)
    issuer = db.Column(db.String(300), nullable=True)
    issued_at = db.Column(db.Date, nullable=True)
    expires_at = db.Column(db.Date, nullable=True)
    credential_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'name': self.name,
            'issuer': self.issuer,
            'issued_at': self.issued_at.isoformat() if self.issued_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'credential_url': self.credential_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
