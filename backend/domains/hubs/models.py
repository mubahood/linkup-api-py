"""
Hubs domain models: Hub, HubMembership, HubPost
"""
import uuid
from datetime import datetime
from backend.models import db


class Hub(db.Model):
    __tablename__ = 'lu_hubs'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = db.Column(db.String(200), unique=True, nullable=False)
    name = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    type = db.Column(db.String(30), default='professional')
    institution_id = db.Column(db.String(36), db.ForeignKey('lu_institutions.id', ondelete='SET NULL'), nullable=True)
    cover_image = db.Column(db.String(500), nullable=True)
    member_count = db.Column(db.Integer, default=0)
    created_by = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    is_public = db.Column(db.SmallInteger, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = db.relationship('Account', foreign_keys=[created_by], lazy='joined')

    def to_dict(self, membership=None):
        return {
            'id': self.id,
            'slug': self.slug,
            'name': self.name,
            'description': self.description,
            'type': self.type,
            'institution_id': self.institution_id,
            'cover_image': self.cover_image,
            'member_count': self.member_count,
            'created_by': self.created_by,
            'is_public': bool(self.is_public),
            'my_role': membership.role if membership else None,
            'is_member': membership is not None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class HubMembership(db.Model):
    __tablename__ = 'lu_hub_memberships'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    hub_id = db.Column(db.String(36), db.ForeignKey('lu_hubs.id', ondelete='CASCADE'), nullable=False)
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    role = db.Column(db.String(20), default='member')
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    account = db.relationship('Account', foreign_keys=[account_id], lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'hub_id': self.hub_id,
            'account_id': self.account_id,
            'role': self.role,
            'account': self.account.to_dict() if self.account else None,
            'joined_at': self.joined_at.isoformat() if self.joined_at else None,
        }


class HubPostLike(db.Model):
    __tablename__ = 'lu_hub_post_likes'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    post_id = db.Column(db.String(36), db.ForeignKey('lu_hub_posts.id', ondelete='CASCADE'), nullable=False)
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    account = db.relationship('Account', foreign_keys=[account_id], lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'post_id': self.post_id,
            'account_id': self.account_id,
            'account': self.account.to_dict() if self.account else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class HubPost(db.Model):
    __tablename__ = 'lu_hub_posts'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    hub_id = db.Column(db.String(36), db.ForeignKey('lu_hubs.id', ondelete='CASCADE'), nullable=False)
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    media = db.Column(db.JSON, nullable=True)
    like_count = db.Column(db.Integer, default=0)
    comment_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)

    author = db.relationship('Account', foreign_keys=[account_id], lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'hub_id': self.hub_id,
            'account_id': self.account_id,
            'content': self.content,
            'media': self.media,
            'like_count': self.like_count,
            'comment_count': self.comment_count,
            'author': self.author.to_dict() if self.author else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
