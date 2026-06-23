"""
Reference domain models: Institution, Org, Location
"""
import uuid
from datetime import datetime
from backend.models import db


class Location(db.Model):
    __tablename__ = 'lu_locations'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(200), nullable=False)
    level = db.Column(db.String(20), default='city')
    parent_id = db.Column(db.String(36), nullable=True)
    country_code = db.Column(db.String(10), default='UG')
    latitude = db.Column(db.Numeric(10, 8), nullable=True)
    longitude = db.Column(db.Numeric(11, 8), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'level': self.level,
            'parent_id': self.parent_id,
            'country_code': self.country_code,
            'latitude': float(self.latitude) if self.latitude else None,
            'longitude': float(self.longitude) if self.longitude else None,
        }


class Institution(db.Model):
    __tablename__ = 'lu_institutions'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(300), nullable=False)
    short_name = db.Column(db.String(100), nullable=True)
    type = db.Column(db.String(30), default='university')
    country = db.Column(db.String(100), default='Uganda')
    district = db.Column(db.String(100), nullable=True)
    website    = db.Column(db.String(300), nullable=True)
    verified   = db.Column(db.SmallInteger, default=0)
    sort_order = db.Column(db.SmallInteger, default=100)
    is_popular = db.Column(db.SmallInteger, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':         self.id,
            'name':       self.name,
            'short_name': self.short_name,
            'type':       self.type,
            'country':    self.country,
            'district':   self.district,
            'website':    self.website,
            'verified':   bool(self.verified),
            'is_popular': bool(self.is_popular),
            'sort_order': self.sort_order,
        }


class Org(db.Model):
    __tablename__ = 'lu_orgs'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(300), nullable=False)
    industry = db.Column(db.String(200), nullable=True)
    size_range = db.Column(db.String(50), nullable=True)
    website = db.Column(db.String(300), nullable=True)
    verified = db.Column(db.SmallInteger, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'industry': self.industry,
            'size_range': self.size_range,
            'website': self.website,
            'verified': bool(self.verified),
        }
