"""
Posts domain service — all business logic for post CRUD, feeds, engagement.
"""
import uuid
from datetime import datetime

from sqlalchemy import or_, and_
from sqlalchemy.orm.attributes import flag_modified

from backend.models import db
from backend.domains.posts.models import (
    Post, PostLike, PostComment, PostCommentLike, PostSave, PollVote,
)
from backend.domains.links.models import Link
from backend.domains.hubs.models import HubMembership
from backend.shared.storage.r2 import save_upload


class PostService:

    # ── Create ────────────────────────────────────────────────────────────────

    @staticmethod
    def create(account, req):
        post_type  = req.form.get('post_type', 'text')
        body       = (req.form.get('body', '') or '').strip() or None
        title      = (req.form.get('title', '') or '').strip() or None
        audience   = req.form.get('audience', 'public')
        mode       = req.form.get('mode', 'professional')
        hub_id     = req.form.get('hub_id') or None
        tags_raw   = req.form.get('tags', '') or ''
        tags       = [t.strip().lstrip('#') for t in tags_raw.split(',') if t.strip()]

        linked_post_id  = req.form.get('linked_post_id') or None
        linked_job_id   = req.form.get('linked_job_id') or None
        linked_event_id = req.form.get('linked_event_id') or None

        # Poll
        poll_question     = (req.form.get('poll_question', '') or '').strip() or None
        poll_options_raw  = req.form.getlist('poll_options')
        poll_options      = None
        if poll_question and poll_options_raw:
            poll_options = [
                {'id': str(uuid.uuid4())[:8], 'text': opt.strip(), 'vote_count': 0}
                for opt in poll_options_raw if opt.strip()
            ]
        poll_ends_at = None
        ends_str = req.form.get('poll_ends_at', '') or ''
        if ends_str:
            try:
                poll_ends_at = datetime.fromisoformat(ends_str)
            except Exception:
                pass

        # Media uploads (up to 5 files)
        media = []
        for f in req.files.getlist('media')[:5]:
            if f and f.filename:
                url = save_upload(f, folder='posts')
                if url:
                    media.append({'url': url, 'type': 'image', 'caption': None})

        now = datetime.utcnow()
        post = Post(
            id=str(uuid.uuid4()),
            author_id=account.id,
            mode=mode,
            post_type=post_type,
            body=body,
            title=title,
            audience=audience,
            hub_id=hub_id,
            linked_post_id=linked_post_id,
            linked_job_id=linked_job_id,
            linked_event_id=linked_event_id,
            media=media or None,
            tags=tags or None,
            poll_question=poll_question,
            poll_options=poll_options,
            poll_ends_at=poll_ends_at,
            created_at=now,
            updated_at=now,
        )
        db.session.add(post)
        db.session.commit()
        db.session.refresh(post)
        return post

    # ── Read helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def get_by_id(post_id):
        return Post.query.filter_by(id=post_id, deleted_at=None).first()

    @staticmethod
    def _connection_ids(account_id):
        """Return set of account IDs the user is connected to (accepted links)."""
        rows = Link.query.filter(
            or_(
                Link.requester_id == account_id,
                Link.addressee_id == account_id,
            ),
            Link.status == 'accepted',
        ).all()
        ids = set()
        for r in rows:
            ids.add(r.addressee_id if r.requester_id == account_id else r.requester_id)
        return ids

    @staticmethod
    def _hub_ids(account_id):
        return {m.hub_id for m in HubMembership.query.filter_by(account_id=account_id).all()}

    @staticmethod
    def _enrich(posts, account_id):
        """Attach my_reaction / my_save / my_vote and resolve reshared posts."""
        if not posts:
            return []
        post_ids = [p.id for p in posts]

        my_reactions = {
            r.post_id: r.reaction_type
            for r in PostLike.query.filter(
                PostLike.post_id.in_(post_ids),
                PostLike.account_id == account_id,
            ).all()
        }
        my_saves = {
            r.post_id
            for r in PostSave.query.filter(
                PostSave.post_id.in_(post_ids),
                PostSave.account_id == account_id,
            ).all()
        }
        my_votes = {
            r.post_id: r.option_id
            for r in PollVote.query.filter(
                PollVote.post_id.in_(post_ids),
                PollVote.account_id == account_id,
            ).all()
        }

        # Resolve reshared originals in one query
        reshare_ids = [p.linked_post_id for p in posts if p.linked_post_id]
        originals = {}
        if reshare_ids:
            for orig in Post.query.filter(Post.id.in_(reshare_ids)).all():
                originals[orig.id] = orig.to_dict()

        return [
            p.to_dict(
                my_reaction=my_reactions.get(p.id),
                my_save=p.id in my_saves,
                my_vote=my_votes.get(p.id),
                shared_post=originals.get(p.linked_post_id) if p.linked_post_id else None,
            )
            for p in posts
        ]

    # ── Feed ─────────────────────────────────────────────────────────────────

    @staticmethod
    def get_feed(account, mode, page, per_page):
        """
        Personal feed (sorted by recency):
        1. The user's own posts (all audience).
        2. Public / connections posts from linked accounts.
        3. Any public post from hub members the user is in.
        4. All other public posts as a fallback (paginated).
        Filtered by mode.
        """
        conn_ids = list(PostService._connection_ids(account.id))
        hub_ids  = list(PostService._hub_ids(account.id))

        q = Post.query.filter(
            Post.deleted_at.is_(None),
            Post.moderation_status == 'approved',
        )

        if mode in ('professional', 'dating'):
            q = q.filter(or_(Post.mode == mode, Post.mode == 'both'))

        q = q.filter(
            or_(
                Post.author_id == account.id,
                and_(
                    Post.author_id.in_(conn_ids) if conn_ids else db.false(),
                    Post.audience.in_(['public', 'connections']),
                ),
                Post.audience == 'public',
                and_(
                    Post.hub_id.isnot(None),
                    Post.hub_id.in_(hub_ids) if hub_ids else db.false(),
                ),
            )
        )

        total = q.count()
        posts = (
            q.order_by(Post.created_at.desc())
             .offset((page - 1) * per_page)
             .limit(per_page)
             .all()
        )
        return PostService._enrich(posts, account.id), total

    @staticmethod
    def get_trending(account, mode, page, per_page):
        """Trending: public posts sorted by engagement in last 72 hours."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=72)

        q = Post.query.filter(
            Post.deleted_at.is_(None),
            Post.moderation_status == 'approved',
            Post.audience == 'public',
            Post.created_at >= cutoff,
        )
        if mode in ('professional', 'dating'):
            q = q.filter(or_(Post.mode == mode, Post.mode == 'both'))

        total = q.count()
        posts = (
            q.order_by((Post.likes_count + Post.comments_count * 2).desc())
             .offset((page - 1) * per_page)
             .limit(per_page)
             .all()
        )
        return PostService._enrich(posts, account.id), total

    @staticmethod
    def get_by_account(viewer_id, account_id, page, per_page):
        """Posts on a profile page — own = all, other = public only."""
        own = viewer_id == account_id
        q = Post.query.filter(
            Post.author_id == account_id,
            Post.deleted_at.is_(None),
            Post.moderation_status == 'approved',
        )
        if not own:
            q = q.filter(Post.audience == 'public')

        total = q.count()
        posts = (
            q.order_by(Post.created_at.desc())
             .offset((page - 1) * per_page)
             .limit(per_page)
             .all()
        )
        return PostService._enrich(posts, viewer_id), total

    @staticmethod
    def get_saved(account, page, per_page):
        total = PostSave.query.filter_by(account_id=account.id).count()
        saves = (
            PostSave.query
            .filter_by(account_id=account.id)
            .order_by(PostSave.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        post_ids = [s.post_id for s in saves]
        posts_map = {
            p.id: p
            for p in Post.query.filter(
                Post.id.in_(post_ids),
                Post.deleted_at.is_(None),
            ).all()
        }
        ordered = [posts_map[pid] for pid in post_ids if pid in posts_map]
        return PostService._enrich(ordered, account.id), total

    # ── Update ────────────────────────────────────────────────────────────────

    @staticmethod
    def update(post, data):
        if 'body' in data:
            post.body = (data['body'] or '').strip() or None
        if 'title' in data:
            post.title = (data['title'] or '').strip() or None
        if 'audience' in data and data['audience'] in ('public', 'connections', 'only_me'):
            post.audience = data['audience']
        if 'tags' in data and isinstance(data['tags'], list):
            post.tags = data['tags']
        # Edit media: replace the post's photo list (e.g. after removing a photo).
        # Accepts a list of {url,type,caption} objects or bare url strings.
        if 'media' in data and isinstance(data['media'], list):
            cleaned = []
            for m in data['media'][:5]:  # same 5-item cap as creation
                if isinstance(m, str) and m.strip():
                    cleaned.append({'url': m.strip(), 'type': 'image', 'caption': None})
                elif isinstance(m, dict) and (m.get('url') or '').strip():
                    cleaned.append({
                        'url': m['url'].strip(),
                        'type': m.get('type') or 'image',
                        'caption': m.get('caption'),
                    })
            post.media = cleaned
            flag_modified(post, 'media')
        post.is_edited = 1
        post.updated_at = datetime.utcnow()
        db.session.commit()
        return post

    # ── Delete ────────────────────────────────────────────────────────────────

    @staticmethod
    def delete(post):
        post.deleted_at = datetime.utcnow()
        db.session.commit()

    # ── Reactions ────────────────────────────────────────────────────────────

    VALID_REACTIONS = {'like', 'love', 'insightful', 'celebrate', 'support'}

    @staticmethod
    def toggle_like(post, account_id, reaction_type='like'):
        if reaction_type not in PostService.VALID_REACTIONS:
            reaction_type = 'like'
        existing = PostLike.query.filter_by(post_id=post.id, account_id=account_id).first()
        if existing:
            if existing.reaction_type == reaction_type:
                db.session.delete(existing)
                post.likes_count = max(0, post.likes_count - 1)
                db.session.commit()
                return None  # removed
            existing.reaction_type = reaction_type
            db.session.commit()
            return reaction_type
        like = PostLike(
            id=str(uuid.uuid4()),
            post_id=post.id,
            account_id=account_id,
            reaction_type=reaction_type,
        )
        db.session.add(like)
        post.likes_count += 1
        db.session.commit()
        return reaction_type

    @staticmethod
    def get_likers(post_id, page, per_page):
        q = PostLike.query.filter_by(post_id=post_id)
        total = q.count()
        likes = (
            q.order_by(PostLike.created_at.desc())
             .offset((page - 1) * per_page)
             .limit(per_page)
             .all()
        )
        return [l.to_dict() for l in likes], total

    # ── Save ─────────────────────────────────────────────────────────────────

    @staticmethod
    def toggle_save(post, account_id):
        existing = PostSave.query.filter_by(post_id=post.id, account_id=account_id).first()
        if existing:
            db.session.delete(existing)
            db.session.commit()
            return False
        db.session.add(PostSave(
            id=str(uuid.uuid4()),
            post_id=post.id,
            account_id=account_id,
        ))
        db.session.commit()
        return True

    # ── Views ────────────────────────────────────────────────────────────────

    @staticmethod
    def register_view(post):
        post.views_count = (post.views_count or 0) + 1
        db.session.commit()

    # ── Reshare ───────────────────────────────────────────────────────────────

    @staticmethod
    def share(original_post, account, body=None):
        now = datetime.utcnow()
        share = Post(
            id=str(uuid.uuid4()),
            author_id=account.id,
            mode=original_post.mode,
            post_type='share',
            body=(body or '').strip() or None,
            audience='public',
            linked_post_id=original_post.id,
            created_at=now,
            updated_at=now,
        )
        db.session.add(share)
        original_post.shares_count = (original_post.shares_count or 0) + 1
        db.session.commit()
        db.session.refresh(share)
        return share

    # ── Comments ─────────────────────────────────────────────────────────────

    @staticmethod
    def get_comments(post_id, account_id, page, per_page):
        """Top-level comments with up to 5 inline replies each."""
        q = PostComment.query.filter_by(post_id=post_id, parent_id=None).filter(
            PostComment.deleted_at.is_(None)
        )
        total = q.count()
        top_level = (
            q.order_by(PostComment.created_at.asc())
             .offset((page - 1) * per_page)
             .limit(per_page)
             .all()
        )

        comment_ids = [c.id for c in top_level]
        my_likes = set()
        if account_id and comment_ids:
            my_likes = {
                r.comment_id
                for r in PostCommentLike.query.filter(
                    PostCommentLike.comment_id.in_(comment_ids),
                    PostCommentLike.account_id == account_id,
                ).all()
            }

        result = []
        for c in top_level:
            d = c.to_dict(my_like=c.id in my_likes)
            replies = (
                PostComment.query
                .filter_by(post_id=post_id, parent_id=c.id)
                .filter(PostComment.deleted_at.is_(None))
                .order_by(PostComment.created_at.asc())
                .limit(5)
                .all()
            )
            d['replies'] = [r.to_dict() for r in replies]
            d['reply_count'] = PostComment.query.filter_by(
                post_id=post_id, parent_id=c.id
            ).count()
            result.append(d)

        return result, total

    @staticmethod
    def add_comment(post, account_id, body, parent_id=None):
        now = datetime.utcnow()
        comment = PostComment(
            id=str(uuid.uuid4()),
            post_id=post.id,
            author_id=account_id,
            parent_id=parent_id,
            body=body.strip(),
            created_at=now,
            updated_at=now,
        )
        db.session.add(comment)
        if not parent_id:
            post.comments_count = (post.comments_count or 0) + 1
        db.session.commit()
        db.session.refresh(comment)
        return comment

    @staticmethod
    def update_comment(comment, body):
        comment.body = body.strip()
        comment.is_edited = 1
        comment.updated_at = datetime.utcnow()
        db.session.commit()
        return comment

    @staticmethod
    def delete_comment(comment, post):
        comment.deleted_at = datetime.utcnow()
        if not comment.parent_id:
            post.comments_count = max(0, (post.comments_count or 1) - 1)
        db.session.commit()

    @staticmethod
    def toggle_comment_like(comment, account_id):
        existing = PostCommentLike.query.filter_by(
            comment_id=comment.id, account_id=account_id
        ).first()
        if existing:
            db.session.delete(existing)
            comment.likes_count = max(0, (comment.likes_count or 1) - 1)
            db.session.commit()
            return False
        db.session.add(PostCommentLike(
            id=str(uuid.uuid4()),
            comment_id=comment.id,
            account_id=account_id,
        ))
        comment.likes_count = (comment.likes_count or 0) + 1
        db.session.commit()
        return True

    # ── Poll ─────────────────────────────────────────────────────────────────

    @staticmethod
    def vote_poll(post, account_id, option_id):
        if post.post_type != 'poll' or not post.poll_options:
            return None, 'Not a poll'
        if post.poll_ends_at and post.poll_ends_at < datetime.utcnow():
            return None, 'Poll has ended'

        valid_ids = [opt['id'] for opt in post.poll_options]
        if option_id not in valid_ids:
            return None, 'Invalid option'

        existing = PollVote.query.filter_by(post_id=post.id, account_id=account_id).first()
        options = list(post.poll_options)  # shallow copy

        if existing:
            if existing.option_id == option_id:
                return options, None  # already voted for same option
            for opt in options:
                if opt['id'] == existing.option_id:
                    opt['vote_count'] = max(0, opt.get('vote_count', 0) - 1)
                if opt['id'] == option_id:
                    opt['vote_count'] = opt.get('vote_count', 0) + 1
            existing.option_id = option_id
        else:
            for opt in options:
                if opt['id'] == option_id:
                    opt['vote_count'] = opt.get('vote_count', 0) + 1
            db.session.add(PollVote(
                id=str(uuid.uuid4()),
                post_id=post.id,
                account_id=account_id,
                option_id=option_id,
            ))

        post.poll_options = options
        flag_modified(post, 'poll_options')
        db.session.commit()
        return post.poll_options, None
