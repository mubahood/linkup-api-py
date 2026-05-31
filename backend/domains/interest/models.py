"""
Interest domain models: InterestTag, InterestProfile
"""
import uuid
from datetime import datetime
from backend.models import db


class InterestTag(db.Model):
    __tablename__ = 'lu_interest_tags'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = db.Column(db.String(200), unique=True, nullable=False)
    dimension = db.Column(db.String(60), nullable=False)
    category_path = db.Column(db.String(500), nullable=True)
    display_name_en = db.Column(db.String(300), nullable=False)
    display_name_lg = db.Column(db.String(300), nullable=True)
    display_name_sw = db.Column(db.String(300), nullable=True)
    aliases = db.Column(db.JSON, nullable=True)
    popularity = db.Column(db.Integer, default=0)
    is_sensitive = db.Column(db.SmallInteger, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'slug': self.slug,
            'dimension': self.dimension,
            'category_path': self.category_path,
            'display_name_en': self.display_name_en,
            'display_name_lg': self.display_name_lg,
            'display_name_sw': self.display_name_sw,
            'aliases': self.aliases,
            'popularity': self.popularity,
            'is_sensitive': bool(self.is_sensitive),
        }


class InterestProfile(db.Model):
    __tablename__ = 'lu_interest_profiles'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    tag_id = db.Column(db.String(36), db.ForeignKey('lu_interest_tags.id', ondelete='CASCADE'), nullable=False)
    weight = db.Column(db.Numeric(5, 4), default=0.5)
    mode = db.Column(db.String(20), default='both')
    pinned = db.Column(db.SmallInteger, default=0)
    source = db.Column(db.String(20), default='explicit')
    last_signaled = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tag = db.relationship('InterestTag', lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'tag_id': self.tag_id,
            'tag': self.tag.to_dict() if self.tag else None,
            'weight': float(self.weight) if self.weight else 0.5,
            'mode': self.mode,
            'pinned': bool(self.pinned),
            'source': self.source,
            'last_signaled': self.last_signaled.isoformat() if self.last_signaled else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
