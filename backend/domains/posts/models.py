"""
Posts domain models.

Post        — universal post (text/photo/article/poll/share etc.)
PostLike    — per-post reactions
PostComment — threaded comments
PostCommentLike — likes on comments
PostSave    — bookmarked posts
PollVote    — poll votes (one per user per post)
"""
import uuid
from datetime import datetime
from backend.models import db


class Post(db.Model):
    __tablename__ = 'lu_posts'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    author_id = db.Column(
        db.String(36),
        db.ForeignKey('lu_accounts.id', ondelete='CASCADE'),
        nullable=False,
    )
    mode = db.Column(db.String(20), nullable=False, default='professional')
    post_type = db.Column(db.String(20), nullable=False, default='text')
    body = db.Column(db.Text, nullable=True)
    title = db.Column(db.String(300), nullable=True)
    audience = db.Column(db.String(20), nullable=False, default='public')
    hub_id = db.Column(
        db.String(36),
        db.ForeignKey('lu_hubs.id', ondelete='SET NULL'),
        nullable=True,
    )
    linked_job_id = db.Column(db.String(36), nullable=True)
    linked_event_id = db.Column(db.String(36), nullable=True)
    linked_post_id = db.Column(db.String(36), nullable=True)
    media = db.Column(db.JSON, nullable=True)
    tags = db.Column(db.JSON, nullable=True)
    poll_question = db.Column(db.String(300), nullable=True)
    poll_options = db.Column(db.JSON, nullable=True)
    poll_ends_at = db.Column(db.DateTime, nullable=True)
    likes_count = db.Column(db.Integer, default=0)
    comments_count = db.Column(db.Integer, default=0)
    shares_count = db.Column(db.Integer, default=0)
    views_count = db.Column(db.Integer, default=0)
    is_pinned = db.Column(db.SmallInteger, default=0)
    is_edited = db.Column(db.SmallInteger, default=0)
    is_featured = db.Column(db.SmallInteger, default=0)
    moderation_status = db.Column(db.String(20), default='approved')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)

    author = db.relationship('Account', foreign_keys=[author_id], lazy='joined')

    def to_dict(self, my_reaction=None, my_save=False, my_vote=None, shared_post=None):
        return {
            'id': self.id,
            'author_id': self.author_id,
            'author': self.author.to_dict() if self.author else None,
            'mode': self.mode,
            'post_type': self.post_type,
            'body': self.body,
            'title': self.title,
            'audience': self.audience,
            'hub_id': self.hub_id,
            'linked_job_id': self.linked_job_id,
            'linked_event_id': self.linked_event_id,
            'linked_post_id': self.linked_post_id,
            'shared_post': shared_post,
            'media': self.media or [],
            'tags': self.tags or [],
            'poll_question': self.poll_question,
            'poll_options': self.poll_options,
            'poll_ends_at': self.poll_ends_at.isoformat() if self.poll_ends_at else None,
            'likes_count': self.likes_count,
            'comments_count': self.comments_count,
            'shares_count': self.shares_count,
            'views_count': self.views_count,
            'is_pinned': bool(self.is_pinned),
            'is_edited': bool(self.is_edited),
            'is_featured': bool(self.is_featured),
            'my_reaction': my_reaction,
            'my_save': my_save,
            'my_vote': my_vote,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class PostLike(db.Model):
    __tablename__ = 'lu_post_likes'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    post_id = db.Column(
        db.String(36),
        db.ForeignKey('lu_posts.id', ondelete='CASCADE'),
        nullable=False,
    )
    account_id = db.Column(
        db.String(36),
        db.ForeignKey('lu_accounts.id', ondelete='CASCADE'),
        nullable=False,
    )
    reaction_type = db.Column(db.String(20), default='like')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    account = db.relationship('Account', foreign_keys=[account_id], lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'post_id': self.post_id,
            'account_id': self.account_id,
            'reaction_type': self.reaction_type,
            'account': self.account.to_dict() if self.account else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class PostComment(db.Model):
    __tablename__ = 'lu_post_comments'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    post_id = db.Column(
        db.String(36),
        db.ForeignKey('lu_posts.id', ondelete='CASCADE'),
        nullable=False,
    )
    author_id = db.Column(
        db.String(36),
        db.ForeignKey('lu_accounts.id', ondelete='CASCADE'),
        nullable=False,
    )
    parent_id = db.Column(db.String(36), nullable=True)
    body = db.Column(db.Text, nullable=False)
    likes_count = db.Column(db.Integer, default=0)
    is_edited = db.Column(db.SmallInteger, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)

    author = db.relationship('Account', foreign_keys=[author_id], lazy='joined')

    def to_dict(self, my_like=False):
        deleted = bool(self.deleted_at)
        return {
            'id': self.id,
            'post_id': self.post_id,
            'author_id': self.author_id,
            'parent_id': self.parent_id,
            'body': self.body if not deleted else '[Comment deleted]',
            'likes_count': self.likes_count,
            'is_edited': bool(self.is_edited),
            'is_deleted': deleted,
            'my_like': my_like,
            'author': self.author.to_dict() if self.author and not deleted else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class PostCommentLike(db.Model):
    __tablename__ = 'lu_post_comment_likes'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    comment_id = db.Column(
        db.String(36),
        db.ForeignKey('lu_post_comments.id', ondelete='CASCADE'),
        nullable=False,
    )
    account_id = db.Column(
        db.String(36),
        db.ForeignKey('lu_accounts.id', ondelete='CASCADE'),
        nullable=False,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PostSave(db.Model):
    __tablename__ = 'lu_post_saves'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    post_id = db.Column(
        db.String(36),
        db.ForeignKey('lu_posts.id', ondelete='CASCADE'),
        nullable=False,
    )
    account_id = db.Column(
        db.String(36),
        db.ForeignKey('lu_accounts.id', ondelete='CASCADE'),
        nullable=False,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PollVote(db.Model):
    __tablename__ = 'lu_poll_votes'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    post_id = db.Column(
        db.String(36),
        db.ForeignKey('lu_posts.id', ondelete='CASCADE'),
        nullable=False,
    )
    account_id = db.Column(
        db.String(36),
        db.ForeignKey('lu_accounts.id', ondelete='CASCADE'),
        nullable=False,
    )
    option_id = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
