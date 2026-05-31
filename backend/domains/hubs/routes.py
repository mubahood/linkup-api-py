"""
Hubs routes: /v1/hubs/*
"""
import uuid
from flask import Blueprint, request
from backend.models import db
from backend.domains.hubs.models import Hub, HubMembership, HubPost, HubPostLike, HubPostComment
from backend.domains.hubs.service import generate_slug
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.utils.response import success_response, error_response, paginated_response
from backend.shared.utils.pagination import paginate_query

hubs_bp = Blueprint('v1_hubs', __name__, url_prefix='/v1/hubs')


def _enrich_hub(hub: Hub, account_id: str) -> dict:
    membership = HubMembership.query.filter_by(hub_id=hub.id, account_id=account_id).first()
    return hub.to_dict(membership)


@hubs_bp.route('', methods=['GET'])
@lu_jwt_required
def list_hubs(account):
    """List hubs: public + my joined."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    filter_type = request.args.get('type', '')
    q = request.args.get('q', '')

    query = Hub.query.filter_by(is_public=1)
    if filter_type:
        query = query.filter(Hub.type == filter_type)
    if q:
        query = query.filter(Hub.name.ilike(f'%{q}%'))
    query = query.order_by(Hub.member_count.desc())

    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([_enrich_hub(h, account.id) for h in items], total, page, per_page, 'Hubs loaded.')


@hubs_bp.route('', methods=['POST'])
@lu_jwt_required
def create_hub(account):
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return error_response('Hub name is required.')

    slug = generate_slug(name)
    hub = Hub(
        id=str(uuid.uuid4()),
        slug=slug,
        name=name,
        description=data.get('description'),
        type=data.get('type', 'professional'),
        institution_id=data.get('institution_id'),
        is_public=int(data.get('is_public', 1)),
        created_by=account.id,
        member_count=1,
    )
    db.session.add(hub)
    db.session.flush()

    # Auto-join as admin
    membership = HubMembership(
        id=str(uuid.uuid4()),
        hub_id=hub.id,
        account_id=account.id,
        role='admin',
    )
    db.session.add(membership)
    db.session.commit()
    return success_response('Hub created.', _enrich_hub(hub, account.id), status_code=201)


@hubs_bp.route('/<hub_id>', methods=['GET'])
@lu_jwt_required
def get_hub(account, hub_id):
    hub = Hub.query.filter(
        (Hub.id == hub_id) | (Hub.slug == hub_id)
    ).first()
    if not hub:
        return error_response('Hub not found.', status_code=404)
    return success_response('Hub loaded.', _enrich_hub(hub, account.id))


@hubs_bp.route('/<hub_id>', methods=['PUT'])
@lu_jwt_required
def update_hub(account, hub_id):
    hub = Hub.query.get(hub_id)
    if not hub:
        return error_response('Hub not found.', status_code=404)
    membership = HubMembership.query.filter_by(hub_id=hub_id, account_id=account.id).first()
    if not membership or membership.role not in ('admin', 'moderator'):
        return error_response('You do not have permission to update this hub.', status_code=403)
    data = request.get_json(silent=True) or {}
    for field in ['name', 'description', 'type', 'cover_image', 'is_public']:
        if field in data:
            setattr(hub, field, data[field])
    db.session.commit()
    return success_response('Hub updated.', _enrich_hub(hub, account.id))


@hubs_bp.route('/<hub_id>/join', methods=['POST'])
@lu_jwt_required
def join_hub(account, hub_id):
    hub = Hub.query.get(hub_id)
    if not hub:
        return error_response('Hub not found.', status_code=404)
    if not hub.is_public:
        return error_response('This hub is private.', status_code=403)
    existing = HubMembership.query.filter_by(hub_id=hub_id, account_id=account.id).first()
    if existing:
        return error_response('You are already a member of this hub.')
    membership = HubMembership(
        id=str(uuid.uuid4()),
        hub_id=hub_id,
        account_id=account.id,
        role='member',
    )
    db.session.add(membership)
    hub.member_count = (hub.member_count or 0) + 1
    db.session.commit()
    return success_response('Joined hub.', membership.to_dict())


@hubs_bp.route('/<hub_id>/leave', methods=['POST'])
@lu_jwt_required
def leave_hub(account, hub_id):
    membership = HubMembership.query.filter_by(hub_id=hub_id, account_id=account.id).first()
    if not membership:
        return error_response('You are not a member of this hub.', status_code=404)
    hub = Hub.query.get(hub_id)
    db.session.delete(membership)
    if hub and hub.member_count > 0:
        hub.member_count -= 1
    db.session.commit()
    return success_response('Left hub.')


@hubs_bp.route('/<hub_id>/members', methods=['GET'])
@lu_jwt_required
def hub_members(account, hub_id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = HubMembership.query.filter_by(hub_id=hub_id).order_by(HubMembership.joined_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([m.to_dict() for m in items], total, page, per_page, 'Members loaded.')


@hubs_bp.route('/<hub_id>/posts', methods=['GET'])
@lu_jwt_required
def hub_posts(account, hub_id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = HubPost.query.filter_by(hub_id=hub_id).filter(
        HubPost.deleted_at.is_(None)
    ).order_by(HubPost.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([p.to_dict() for p in items], total, page, per_page, 'Posts loaded.')


@hubs_bp.route('/<hub_id>/posts', methods=['POST'])
@lu_jwt_required
def create_post(account, hub_id):
    membership = HubMembership.query.filter_by(hub_id=hub_id, account_id=account.id).first()
    if not membership:
        return error_response('You must be a member to post.', status_code=403)
    data = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()
    if not content:
        return error_response('Post content is required.')
    post = HubPost(
        id=str(uuid.uuid4()),
        hub_id=hub_id,
        account_id=account.id,
        content=content,
        media=data.get('media'),
    )
    db.session.add(post)
    db.session.commit()
    return success_response('Post created.', post.to_dict(), status_code=201)


@hubs_bp.route('/<hub_id>/posts/<post_id>/like', methods=['POST'])
@lu_jwt_required
def like_post(account, hub_id, post_id):
    """Toggle like on a hub post."""
    post = HubPost.query.filter_by(id=post_id, hub_id=hub_id).filter(
        HubPost.deleted_at.is_(None)
    ).first()
    if not post:
        return error_response('Post not found.', status_code=404)
    existing = HubPostLike.query.filter_by(post_id=post_id, account_id=account.id).first()
    if existing:
        # Unlike
        db.session.delete(existing)
        post.like_count = max(0, (post.like_count or 0) - 1)
        db.session.commit()
        return success_response('Post unliked.', {'liked': False, 'like_count': post.like_count})
    # Like
    like = HubPostLike(
        id=str(uuid.uuid4()),
        post_id=post_id,
        account_id=account.id,
    )
    db.session.add(like)
    post.like_count = (post.like_count or 0) + 1
    db.session.commit()
    # Notify the post author (skip self-like)
    if post.account_id != account.id:
        try:
            from backend.domains.notifications.service import create_notification
            create_notification(
                account_id=post.account_id,
                notif_type='post.liked',
                title=f'{account.display_name} liked your post',
                body=post.content[:80] if post.content else '',
                data={'post_id': post_id, 'hub_id': hub_id, 'liker_id': account.id},
                action_url=f'/hubs/{hub_id}',
            )
        except Exception:
            pass
    return success_response('Post liked.', {'liked': True, 'like_count': post.like_count})


@hubs_bp.route('/<hub_id>/posts/<post_id>/likes', methods=['GET'])
@lu_jwt_required
def post_likes(account, hub_id, post_id):
    """List accounts who liked a post."""
    post = HubPost.query.filter_by(id=post_id, hub_id=hub_id).first()
    if not post:
        return error_response('Post not found.', status_code=404)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = HubPostLike.query.filter_by(post_id=post_id).order_by(HubPostLike.created_at.desc())
    from backend.shared.utils.pagination import paginate_query
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([l.to_dict() for l in items], total, page, per_page, 'Likes loaded.')


@hubs_bp.route('/<hub_id>/posts/<post_id>', methods=['PUT'])
@lu_jwt_required
def edit_post(account, hub_id, post_id):
    """Edit a hub post — author only."""
    post = HubPost.query.filter_by(id=post_id, hub_id=hub_id).filter(
        HubPost.deleted_at.is_(None)
    ).first()
    if not post:
        return error_response('Post not found.', status_code=404)
    if post.account_id != account.id:
        return error_response('You can only edit your own posts.', status_code=403)
    data = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()
    if not content:
        return error_response('Post content is required.')
    post.content = content
    if 'media' in data:
        post.media = data['media']
    db.session.commit()
    return success_response('Post updated.', post.to_dict())


@hubs_bp.route('/<hub_id>/posts/<post_id>/comments', methods=['GET'])
@lu_jwt_required
def list_comments(account, hub_id, post_id):
    """List comments on a hub post."""
    post = HubPost.query.filter_by(id=post_id, hub_id=hub_id).filter(
        HubPost.deleted_at.is_(None)
    ).first()
    if not post:
        return error_response('Post not found.', status_code=404)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    # Top-level comments only (no parent_id), include soft-deleted for threading
    query = HubPostComment.query.filter_by(post_id=post_id, parent_id=None).order_by(
        HubPostComment.created_at.asc()
    )
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)

    result = []
    for comment in items:
        d = comment.to_dict()
        # Attach replies (one level deep for Phase 1)
        replies = HubPostComment.query.filter_by(
            post_id=post_id, parent_id=comment.id
        ).order_by(HubPostComment.created_at.asc()).limit(5).all()
        d['replies'] = [r.to_dict() for r in replies]
        d['reply_count'] = HubPostComment.query.filter_by(
            post_id=post_id, parent_id=comment.id
        ).filter(HubPostComment.deleted_at.is_(None)).count()
        result.append(d)

    return paginated_response(result, total, page, per_page, 'Comments loaded.')


@hubs_bp.route('/<hub_id>/posts/<post_id>/comments', methods=['POST'])
@lu_jwt_required
def create_comment(account, hub_id, post_id):
    """Create a comment on a hub post."""
    post = HubPost.query.filter_by(id=post_id, hub_id=hub_id).filter(
        HubPost.deleted_at.is_(None)
    ).first()
    if not post:
        return error_response('Post not found.', status_code=404)
    # Must be a hub member to comment
    membership = HubMembership.query.filter_by(hub_id=hub_id, account_id=account.id).first()
    if not membership:
        return error_response('You must be a hub member to comment.', status_code=403)
    data = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()
    if not content:
        return error_response('Comment content is required.')
    parent_id = data.get('parent_id')  # optional — reply to another comment
    if parent_id:
        parent = HubPostComment.query.filter_by(id=parent_id, post_id=post_id).filter(
            HubPostComment.deleted_at.is_(None)
        ).first()
        if not parent:
            return error_response('Parent comment not found.', status_code=404)

    comment = HubPostComment(
        id=str(uuid.uuid4()),
        post_id=post_id,
        account_id=account.id,
        parent_id=parent_id,
        content=content,
    )
    db.session.add(comment)
    # Update comment_count on post
    post.comment_count = (post.comment_count or 0) + 1
    db.session.commit()

    # Notify post author (skip self)
    if post.account_id != account.id:
        try:
            from backend.domains.notifications.service import create_notification
            create_notification(
                account_id=post.account_id,
                notif_type='post.commented',
                title=f'{account.display_name} commented on your post',
                body=content[:80],
                data={'post_id': post_id, 'hub_id': hub_id, 'comment_id': comment.id},
                action_url=f'/hubs/{hub_id}/posts/{post_id}',
            )
        except Exception:
            pass

    return success_response('Comment posted.', comment.to_dict(), status_code=201)


@hubs_bp.route('/<hub_id>/posts/<post_id>/comments/<comment_id>', methods=['PUT'])
@lu_jwt_required
def edit_comment(account, hub_id, post_id, comment_id):
    """Edit a comment — author only."""
    comment = HubPostComment.query.filter_by(id=comment_id, post_id=post_id).filter(
        HubPostComment.deleted_at.is_(None)
    ).first()
    if not comment:
        return error_response('Comment not found.', status_code=404)
    if comment.account_id != account.id:
        return error_response('You can only edit your own comments.', status_code=403)
    data = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()
    if not content:
        return error_response('Comment content is required.')
    comment.content = content
    db.session.commit()
    return success_response('Comment updated.', comment.to_dict())


@hubs_bp.route('/<hub_id>/posts/<post_id>/comments/<comment_id>', methods=['DELETE'])
@lu_jwt_required
def delete_comment(account, hub_id, post_id, comment_id):
    """Soft-delete a comment — author, hub admin, or moderator."""
    comment = HubPostComment.query.filter_by(id=comment_id, post_id=post_id).filter(
        HubPostComment.deleted_at.is_(None)
    ).first()
    if not comment:
        return error_response('Comment not found.', status_code=404)
    membership = HubMembership.query.filter_by(hub_id=hub_id, account_id=account.id).first()
    if comment.account_id != account.id and (not membership or membership.role not in ('admin', 'moderator')):
        return error_response('You cannot delete this comment.', status_code=403)
    from datetime import datetime
    comment.deleted_at = datetime.utcnow()
    # Decrement post comment_count
    post = HubPost.query.get(post_id)
    if post and post.comment_count > 0:
        post.comment_count -= 1
    db.session.commit()
    return success_response('Comment deleted.')


@hubs_bp.route('/<hub_id>/posts/<post_id>', methods=['DELETE'])
@lu_jwt_required
def delete_post(account, hub_id, post_id):
    post = HubPost.query.filter_by(id=post_id, hub_id=hub_id).first()
    if not post:
        return error_response('Post not found.', status_code=404)
    membership = HubMembership.query.filter_by(hub_id=hub_id, account_id=account.id).first()
    if post.account_id != account.id and (not membership or membership.role not in ('admin', 'moderator')):
        return error_response('You cannot delete this post.', status_code=403)
    from datetime import datetime
    post.deleted_at = datetime.utcnow()
    db.session.commit()
    return success_response('Post deleted.')
