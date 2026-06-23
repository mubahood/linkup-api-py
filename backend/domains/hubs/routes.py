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
    """
    List hubs: public + my joined.
    Filters: ?type=professional|social, ?q=text, ?institution_id=UUID, ?mine=true
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    filter_type = request.args.get('type', '')
    q = request.args.get('q', '')
    institution_id = request.args.get('institution_id', '')
    mine = request.args.get('mine', '').lower() == 'true'

    if mine:
        # Only hubs I'm a member of
        my_hub_ids = [r[0] for r in db.session.query(HubMembership.hub_id).filter_by(
            account_id=account.id
        ).all()]
        query = Hub.query.filter(Hub.id.in_(my_hub_ids)) if my_hub_ids else Hub.query.filter_by(id=None)
    else:
        query = Hub.query.filter_by(is_public=1)

    if filter_type:
        query = query.filter(Hub.type == filter_type)
    if q:
        query = query.filter(Hub.name.ilike(f'%{q}%'))
    if institution_id:
        query = query.filter(Hub.institution_id == institution_id)
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


@hubs_bp.route('/mine', methods=['GET'])
@lu_jwt_required
def my_hubs(account):
    """Hubs I am a member of (convenience alias for ?mine=true)."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    my_hub_ids = [r[0] for r in db.session.query(HubMembership.hub_id).filter_by(
        account_id=account.id
    ).all()]
    if not my_hub_ids:
        return paginated_response([], 0, page, per_page, 'My hubs loaded.')
    query = Hub.query.filter(Hub.id.in_(my_hub_ids)).order_by(Hub.member_count.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([_enrich_hub(h, account.id) for h in items], total, page, per_page, 'My hubs loaded.')


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

    # Attach headline from ProfessionalProfile for each member
    from backend.domains.profile.models import ProfessionalProfile
    account_ids = [m.account_id for m in items]
    profiles = {
        p.account_id: p
        for p in ProfessionalProfile.query.filter(
            ProfessionalProfile.account_id.in_(account_ids)
        ).all()
    } if account_ids else {}

    result = []
    for m in items:
        d = m.to_dict()
        prof = profiles.get(m.account_id)
        if d.get('account') and prof:
            d['account']['headline'] = prof.headline or ''
        result.append(d)

    return paginated_response(result, total, page, per_page, 'Members loaded.')


@hubs_bp.route('/<hub_id>/invite', methods=['POST'])
@lu_jwt_required
def invite_to_hub(account, hub_id):
    """
    Invite a LinkUp member to a hub (admin/moderator only for private hubs;
    any member can invite to public hubs).
    Body: { account_id: "<uuid>" }
    """
    hub = Hub.query.get(hub_id)
    if not hub:
        return error_response('Hub not found.', status_code=404)

    my_membership = HubMembership.query.filter_by(hub_id=hub_id, account_id=account.id).first()
    if not my_membership:
        return error_response('You must be a member to invite others.', status_code=403)
    if not hub.is_public and my_membership.role not in ('admin', 'moderator'):
        return error_response('Only admins and moderators can invite to private hubs.', status_code=403)

    data = request.get_json(silent=True) or {}
    invitee_id = (data.get('account_id') or '').strip()
    if not invitee_id:
        return error_response('account_id is required.')
    if invitee_id == account.id:
        return error_response('You cannot invite yourself.')

    from backend.domains.identity.models import Account as Acct
    invitee = db.session.get(Acct, invitee_id)
    if not invitee or invitee.deleted_at:
        return error_response('Account not found.', status_code=404)

    existing = HubMembership.query.filter_by(hub_id=hub_id, account_id=invitee_id).first()
    if existing:
        return error_response('This person is already a member of this hub.')

    # Notify the invitee
    try:
        from backend.domains.notifications.service import create_notification
        create_notification(
            account_id=invitee_id,
            notif_type='hub.invited',
            title=f'{account.display_name} invited you to {hub.name}',
            body=hub.description[:80] if hub.description else f'Join {hub.name} on LinkUp!',
            data={'hub_id': hub_id, 'inviter_id': account.id},
            action_url=f'/hubs/{hub_id}',
        )
    except Exception:
        pass

    return success_response(
        f'Invitation sent to {invitee.display_name}.',
        {'hub_id': hub_id, 'invited_account_id': invitee_id, 'invited_name': invitee.display_name},
    )


@hubs_bp.route('/<hub_id>/posts', methods=['GET'])
@lu_jwt_required
def hub_posts(account, hub_id):
    page     = request.args.get('page',     1,  type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = HubPost.query.filter_by(hub_id=hub_id).filter(
        HubPost.deleted_at.is_(None)
    ).order_by(HubPost.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)

    # Batch-fetch my likes for the returned posts in one query
    post_ids = [p.id for p in items]
    liked_ids = {
        like.post_id
        for like in HubPostLike.query.filter(
            HubPostLike.post_id.in_(post_ids),
            HubPostLike.account_id == account.id,
        ).all()
    } if post_ids else set()

    result = []
    for p in items:
        d = p.to_dict(my_like=(p.id in liked_ids))
        # Attach author headline from ProfessionalProfile
        try:
            from backend.domains.profile.models import ProfessionalProfile
            prof = ProfessionalProfile.query.filter_by(account_id=p.account_id).first()
            if d.get('author') and prof:
                d['author']['headline'] = prof.headline or ''
        except Exception:
            pass
        result.append(d)

    return paginated_response(result, total, page, per_page, 'Posts loaded.')


@hubs_bp.route('/<hub_id>/posts/<post_id>', methods=['GET'])
@lu_jwt_required
def get_post(account, hub_id, post_id):
    """Single post detail — includes like status, comment count, and first page of comments."""
    post = HubPost.query.filter_by(id=post_id, hub_id=hub_id).filter(
        HubPost.deleted_at.is_(None)
    ).first()
    if not post:
        return error_response('Post not found.', status_code=404)
    my_like = HubPostLike.query.filter_by(post_id=post_id, account_id=account.id).first()
    data = post.to_dict(my_like=bool(my_like))
    # Inline first page of comments for convenience
    top_comments = HubPostComment.query.filter_by(post_id=post_id, parent_id=None).filter(
        HubPostComment.deleted_at.is_(None)
    ).order_by(HubPostComment.created_at.asc()).limit(5).all()
    data['comments'] = []
    for c in top_comments:
        cd = c.to_dict()
        replies = HubPostComment.query.filter_by(post_id=post_id, parent_id=c.id).filter(
            HubPostComment.deleted_at.is_(None)
        ).limit(3).all()
        cd['replies'] = [r.to_dict() for r in replies]
        data['comments'].append(cd)
    data['comment_count'] = post.comment_count
    data['has_more_comments'] = post.comment_count > 5
    return success_response('Post loaded.', data)


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


# ── Admin: delete hub ─────────────────────────────────────────────────────────

@hubs_bp.route('/<hub_id>', methods=['DELETE'])
@lu_jwt_required
def delete_hub(account, hub_id):
    """Permanently delete a hub — creator or admin member only."""
    hub = db.session.get(Hub, hub_id)
    if not hub:
        return error_response('Hub not found.', status_code=404)
    membership = HubMembership.query.filter_by(hub_id=hub_id, account_id=account.id).first()
    if hub.created_by != account.id and (not membership or membership.role != 'admin'):
        return error_response('Only the hub creator or an admin can delete this hub.', status_code=403)
    db.session.delete(hub)
    db.session.commit()
    return success_response('Hub deleted.')


# ── Admin: change member role ─────────────────────────────────────────────────

@hubs_bp.route('/<hub_id>/members/<member_account_id>/role', methods=['PUT'])
@lu_jwt_required
def change_member_role(account, hub_id, member_account_id):
    """
    PUT /v1/hubs/<hub_id>/members/<account_id>/role
    Body: { role: member | moderator | admin }
    Admin only.
    """
    my_membership = HubMembership.query.filter_by(hub_id=hub_id, account_id=account.id).first()
    if not my_membership or my_membership.role != 'admin':
        return error_response('Only hub admins can change member roles.', status_code=403)

    target = HubMembership.query.filter_by(hub_id=hub_id, account_id=member_account_id).first()
    if not target:
        return error_response('Member not found in this hub.', status_code=404)
    if member_account_id == account.id:
        return error_response('You cannot change your own role.')

    data = request.get_json(silent=True) or {}
    new_role = (data.get('role') or '').strip()
    if new_role not in ('member', 'moderator', 'admin'):
        return error_response('role must be: member, moderator, or admin')

    target.role = new_role
    db.session.commit()
    return success_response('Member role updated.', target.to_dict())


# ── Admin: remove (kick) a member ────────────────────────────────────────────

@hubs_bp.route('/<hub_id>/members/<member_account_id>', methods=['DELETE'])
@lu_jwt_required
def remove_member(account, hub_id, member_account_id):
    """
    DELETE /v1/hubs/<hub_id>/members/<account_id>
    Admin or moderator can remove members (mods cannot remove admins).
    """
    my_membership = HubMembership.query.filter_by(hub_id=hub_id, account_id=account.id).first()
    if not my_membership or my_membership.role not in ('admin', 'moderator'):
        return error_response('Only hub admins and moderators can remove members.', status_code=403)
    if member_account_id == account.id:
        return error_response('Use /leave to remove yourself from a hub.')

    target = HubMembership.query.filter_by(hub_id=hub_id, account_id=member_account_id).first()
    if not target:
        return error_response('Member not found in this hub.', status_code=404)

    # Moderators cannot kick admins
    if my_membership.role == 'moderator' and target.role == 'admin':
        return error_response('Moderators cannot remove admins.', status_code=403)

    hub = db.session.get(Hub, hub_id)
    db.session.delete(target)
    if hub and hub.member_count > 0:
        hub.member_count -= 1
    db.session.commit()
    return success_response('Member removed from hub.')
