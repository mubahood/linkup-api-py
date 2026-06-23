import uuid
from datetime import datetime
from backend.models import db


class UserPhoto(db.Model):
    __tablename__ = 'lu_user_photos'

    id               = db.Column(db.String(36), primary_key=True,
                                 default=lambda: str(uuid.uuid4()))
    account_id       = db.Column(db.String(36),
                                 db.ForeignKey('lu_accounts.id', ondelete='CASCADE'),
                                 nullable=False, index=True)
    url              = db.Column(db.String(500), nullable=False)
    is_profile_photo = db.Column(db.Boolean, nullable=False, default=False)
    is_cover_photo   = db.Column(db.Boolean, nullable=False, default=False)
    is_public        = db.Column(db.Boolean, nullable=False, default=True)
    caption          = db.Column(db.String(300), nullable=True)
    photo_type       = db.Column(db.String(50), nullable=False, default='gallery')
    sort_order       = db.Column(db.SmallInteger, nullable=False, default=0)
    created_at       = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, nullable=False,
                                 default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id':               self.id,
            'url':              self.url,
            'is_profile_photo': bool(self.is_profile_photo),
            'is_cover_photo':   bool(self.is_cover_photo),
            'is_public':        bool(self.is_public),
            'caption':          self.caption,
            'photo_type':       self.photo_type,
            'sort_order':       self.sort_order,
            'created_at':       self.created_at.isoformat() if self.created_at else None,
        }
