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
    profile_views = db.Column(db.Integer, default=0)
    # ── 360° depth (T-API-100) ──────────────────────────────────────────────
    pronouns = db.Column(db.String(30), nullable=True)
    tagline = db.Column(db.String(160), nullable=True)
    industry = db.Column(db.String(120), nullable=True)
    years_experience = db.Column(db.Integer, nullable=True)
    availability_status = db.Column(db.String(30), default='open')  # open|casually_looking|not_looking
    social_links = db.Column(db.JSON, nullable=True)       # {linkedin,github,x,website,...}
    portfolio_urls = db.Column(db.JSON, nullable=True)     # [url, ...]
    achievements = db.Column(db.JSON, nullable=True)       # [{title, year?}, ...]
    languages_spoken = db.Column(db.JSON, nullable=True)   # [{code, proficiency}, ...]
    location_origin_id = db.Column(db.String(36), nullable=True)  # "where you're from"
    hourly_rate = db.Column(db.Integer, nullable=True)
    hourly_rate_currency = db.Column(db.String(8), default='UGX')
    response_rate = db.Column(db.Float, nullable=True)     # computed trust signal
    profile_video_url = db.Column(db.String(500), nullable=True)
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
            'profile_views': self.profile_views or 0,
            # 360° depth
            'pronouns': self.pronouns,
            'tagline': self.tagline,
            'industry': self.industry,
            'years_experience': self.years_experience,
            'availability_status': self.availability_status or 'open',
            'social_links': self.social_links or {},
            'portfolio_urls': self.portfolio_urls or [],
            'achievements': self.achievements or [],
            'languages_spoken': self.languages_spoken or [],
            'location_origin_id': self.location_origin_id,
            'hourly_rate': self.hourly_rate,
            'hourly_rate_currency': self.hourly_rate_currency or 'UGX',
            'response_rate': self.response_rate,
            'profile_video_url': self.profile_video_url,
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
    birth_year = db.Column(db.SmallInteger, nullable=True)
    discoverability = db.Column(db.String(20), default='discoverable')
    gender = db.Column(db.String(30), nullable=True)
    looking_for_gender = db.Column(db.String(30), nullable=True)
    intent = db.Column(db.String(30), default='open')
    lifestyle = db.Column(db.JSON, nullable=True)
    prompts = db.Column(db.JSON, nullable=True)
    photos = db.Column(db.JSON, nullable=True)          # list of {url, caption?}
    max_distance_km = db.Column(db.SmallInteger, nullable=True)
    # ── 360° depth (T-API-101) ──────────────────────────────────────────────
    height_cm = db.Column(db.Integer, nullable=True)
    relationship_goal = db.Column(db.String(30), nullable=True)
    has_children = db.Column(db.String(20), nullable=True)
    wants_children = db.Column(db.String(20), nullable=True)
    smoking = db.Column(db.String(20), nullable=True)
    drinking = db.Column(db.String(20), nullable=True)
    religion = db.Column(db.String(60), nullable=True)        # sensitive
    religiosity = db.Column(db.String(30), nullable=True)     # sensitive
    tribe_ethnicity = db.Column(db.String(60), nullable=True)  # sensitive
    education_level = db.Column(db.String(40), nullable=True)
    love_languages = db.Column(db.JSON, nullable=True)
    personality_type = db.Column(db.String(8), nullable=True)
    diet = db.Column(db.String(40), nullable=True)
    exercise = db.Column(db.String(30), nullable=True)
    pets = db.Column(db.JSON, nullable=True)
    voice_prompt_url = db.Column(db.String(500), nullable=True)
    deal_breakers = db.Column(db.JSON, nullable=True)
    sensitive_optin = db.Column(db.JSON, nullable=True)       # {"religion": true, ...}
    # ── Deeper attributes (P-API-03) ────────────────────────────────────────
    sexual_orientation = db.Column(db.String(30), nullable=True)
    marijuana = db.Column(db.String(20), nullable=True)
    politics = db.Column(db.String(30), nullable=True)        # sensitive
    body_type = db.Column(db.String(30), nullable=True)
    zodiac = db.Column(db.String(20), nullable=True)
    communication_style = db.Column(db.String(30), nullable=True)
    languages_spoken = db.Column(db.JSON, nullable=True)
    industry = db.Column(db.String(40), nullable=True)
    region_id = db.Column(db.String(36), nullable=True)
    district_id = db.Column(db.String(36), nullable=True)
    country_code = db.Column(db.String(10), default='UG')
    # ── Preferences / "looking for" (P-API-04) ──────────────────────────────
    preferences = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Fields hidden from non-owner views unless the member opted them in.
    SENSITIVE_FIELDS = ('religion', 'religiosity', 'tribe_ethnicity', 'politics')

    # All attribute fields the wizard captures (used by the step API + matcher).
    ATTRIBUTE_FIELDS = (
        'gender', 'sexual_orientation', 'birth_year', 'height_cm', 'body_type',
        'relationship_goal', 'intent', 'has_children', 'wants_children',
        'smoking', 'drinking', 'marijuana', 'diet', 'exercise', 'pets',
        'religion', 'religiosity', 'politics', 'tribe_ethnicity',
        'education_level', 'industry', 'languages_spoken', 'zodiac',
        'personality_type', 'love_languages', 'communication_style',
        'region_id', 'district_id', 'country_code',
    )

    def _location_label(self):
        """Human label for the saved area, e.g. "Kampala, Central" — resolved
        from the district (and its parent region) names. None if nothing set."""
        if not self.district_id and not self.region_id:
            return None
        try:
            from backend.domains.reference.models import Location
            names = []
            if self.district_id:
                d = Location.query.get(self.district_id)
                if d:
                    names.append(d.name)
            if self.region_id:
                r = Location.query.get(self.region_id)
                if r and r.name not in names:
                    names.append(r.name)
            return ', '.join(names) if names else None
        except Exception:
            return None

    def to_dict(self, include_sensitive=True):
        """Serialize the dating profile.

        `include_sensitive=True` (owner view) returns everything. For other
        viewers pass `include_sensitive=False`: sensitive values appear only for
        the specific fields the member opted into via `sensitive_optin`.
        These fields must never reach a professional surface (mode separation).
        """
        from datetime import date
        from backend.shared.json_safe import as_obj
        age = None
        if self.birth_year:
            age = date.today().year - self.birth_year
        optin = as_obj(self.sensitive_optin)
        d = {
            'id': self.id,
            'account_id': self.account_id,
            'display_name': self.display_name,
            'bio': self.bio,
            'age': age,
            'birth_year': self.birth_year,
            'age_min': self.age_min,
            'age_max': self.age_max,
            'discoverability': self.discoverability or 'discoverable',
            'gender': self.gender,
            'looking_for_gender': self.looking_for_gender,
            'intent': self.intent,
            'lifestyle': self.lifestyle,
            'prompts': self.prompts,
            'photos': self.photos or [],
            'max_distance_km': self.max_distance_km,
            # 360° depth
            'height_cm': self.height_cm,
            'relationship_goal': self.relationship_goal,
            'has_children': self.has_children,
            'wants_children': self.wants_children,
            'smoking': self.smoking,
            'drinking': self.drinking,
            'education_level': self.education_level,
            'love_languages': self.love_languages or [],
            'personality_type': self.personality_type,
            'diet': self.diet,
            'exercise': self.exercise,
            'pets': self.pets or [],
            'voice_prompt_url': self.voice_prompt_url,
            'deal_breakers': self.deal_breakers or [],
            'sensitive_optin': optin,
            # Deeper attributes (P-API-03)
            'sexual_orientation': self.sexual_orientation,
            'marijuana': self.marijuana,
            'body_type': self.body_type,
            'zodiac': self.zodiac,
            'communication_style': self.communication_style,
            'languages_spoken': self.languages_spoken or [],
            'industry': self.industry,
            'region_id': self.region_id,
            'district_id': self.district_id,
            'location_label': self._location_label(),
            'country_code': self.country_code or 'UG',
            # Preferences ("looking for") are owner-only by default.
            'preferences': as_obj(self.preferences) if include_sensitive else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        for f in self.SENSITIVE_FIELDS:
            d[f] = getattr(self, f) if (include_sensitive or optin.get(f)) else None
        return d


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
