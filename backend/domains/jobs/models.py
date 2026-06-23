"""
Jobs domain models: Job, Application, SavedJob
"""
import uuid
from datetime import datetime
from backend.models import db


class Job(db.Model):
    __tablename__ = 'lu_jobs'

    id              = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id          = db.Column(db.String(36), db.ForeignKey('lu_orgs.id', ondelete='SET NULL'), nullable=True)
    org_name        = db.Column(db.String(300), nullable=True)
    posted_by       = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    title           = db.Column(db.String(300), nullable=False)
    description     = db.Column(db.Text, nullable=True)
    requirements    = db.Column(db.JSON, nullable=True)   # list[str]
    location_id     = db.Column(db.String(36), db.ForeignKey('lu_locations.id', ondelete='SET NULL'), nullable=True)
    location_text   = db.Column(db.String(300), nullable=True)
    work_mode       = db.Column(db.String(20), default='onsite')   # onsite | remote | hybrid
    employment_type = db.Column(db.String(30), default='full_time')
    seniority       = db.Column(db.String(30), default='entry')
    salary_min      = db.Column(db.Numeric(12, 2), nullable=True)
    salary_max      = db.Column(db.Numeric(12, 2), nullable=True)
    currency        = db.Column(db.String(10), default='UGX')
    skills          = db.Column(db.JSON, nullable=True)   # list[str]
    is_open         = db.Column(db.SmallInteger, default=1)
    referral_open   = db.Column(db.SmallInteger, default=0)
    view_count      = db.Column(db.Integer, default=0)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at      = db.Column(db.DateTime, nullable=True)

    poster = db.relationship('Account', foreign_keys=[posted_by], lazy='joined')

    # ── salary display helper ──────────────────────────────────────────────
    @property
    def salary_display(self) -> str:
        if not self.salary_min and not self.salary_max:
            return ''
        cur = self.currency or 'UGX'

        def _fmt(n):
            if n >= 1_000_000:
                return f'{n / 1_000_000:.1f}M'
            if n >= 1_000:
                return f'{n / 1_000:.0f}K'
            return str(int(n))

        if self.salary_min and self.salary_max:
            return f'{cur} {_fmt(float(self.salary_min))} – {_fmt(float(self.salary_max))}'
        if self.salary_min:
            return f'{cur} {_fmt(float(self.salary_min))}+'
        return f'Up to {cur} {_fmt(float(self.salary_max))}'

    def to_dict(self, is_saved=False, application=None, include_application_count=False):
        poster_data = None
        if self.poster:
            poster_data = self.poster.to_dict()
            # Enrich with professional headline in one query
            try:
                from backend.domains.profile.models import ProfessionalProfile
                prof = ProfessionalProfile.query.filter_by(account_id=self.poster.id).first()
                if prof:
                    poster_data['headline']     = prof.headline or ''
                    poster_data['current_role'] = prof.current_role or ''
            except Exception:
                pass

        d = {
            'id':               self.id,
            'org_id':           self.org_id,
            'org_name':         self.org_name,
            'posted_by':        self.posted_by,
            'poster':           poster_data,
            'title':            self.title,
            'description':      self.description,
            'requirements':     self.requirements or [],
            'location_id':      self.location_id,
            'location_text':    self.location_text,
            'work_mode':        self.work_mode,
            'employment_type':  self.employment_type,
            'seniority':        self.seniority,
            'salary_min':       float(self.salary_min)  if self.salary_min  else None,
            'salary_max':       float(self.salary_max)  if self.salary_max  else None,
            'salary_display':   self.salary_display,
            'currency':         self.currency,
            'skills':           self.skills or [],
            'is_open':          bool(self.is_open),
            'referral_open':    bool(self.referral_open),
            'view_count':       self.view_count or 0,
            'is_saved':         is_saved,
            'my_application':   application.to_dict() if application else None,
            'created_at':       self.created_at.isoformat() if self.created_at else None,
            'updated_at':       self.updated_at.isoformat() if self.updated_at else None,
            'expires_at':       self.expires_at.isoformat() if self.expires_at else None,
        }
        if include_application_count:
            d['application_count'] = Application.query.filter_by(job_id=self.id).count()
        return d


class Application(db.Model):
    __tablename__ = 'lu_applications'

    id           = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id       = db.Column(db.String(36), db.ForeignKey('lu_jobs.id', ondelete='CASCADE'), nullable=False)
    applicant_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    cover_note   = db.Column(db.Text, nullable=True)
    status       = db.Column(db.String(20), default='applied')
    # applied | shortlisted | interview | hired | rejected | withdrawn
    referred_by  = db.Column(db.String(36), nullable=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    applicant = db.relationship('Account', foreign_keys=[applicant_id], lazy='joined')

    def to_dict(self):
        applicant_data = None
        if self.applicant:
            applicant_data = self.applicant.to_dict()
            try:
                from backend.domains.profile.models import ProfessionalProfile
                prof = ProfessionalProfile.query.filter_by(account_id=self.applicant.id).first()
                if prof:
                    applicant_data['headline'] = prof.headline or ''
            except Exception:
                pass
        return {
            'id':           self.id,
            'job_id':       self.job_id,
            'applicant_id': self.applicant_id,
            'cover_note':   self.cover_note,
            'status':       self.status,
            'referred_by':  self.referred_by,
            'applicant':    applicant_data,
            'created_at':   self.created_at.isoformat() if self.created_at else None,
            'updated_at':   self.updated_at.isoformat() if self.updated_at else None,
        }


class SavedJob(db.Model):
    __tablename__ = 'lu_saved_jobs'

    id         = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id     = db.Column(db.String(36), db.ForeignKey('lu_jobs.id', ondelete='CASCADE'), nullable=False)
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
