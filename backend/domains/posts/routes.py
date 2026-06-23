"""
Posts blueprint — /v1/posts and /v1/comments.
"""
from flask import Blueprint, request

from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.utils.response import success_response, error_response, paginated_response
from backend.domains.posts.service import PostService
from backend.domains.posts.models import PostComment

posts_bp = Blueprint('posts', __name__)


def _pagination():
    page     = max(1, int(request.args.get('page', 1)))
    per_page = min(50, max(5, int(request.args.get('per_page', 20))))
    return page, per_page


# ── Create post ───────────────────────────────────────────────────────────────

@posts_bp.route('/v1/posts', methods=['POST'])
@lu_jwt_required
def create_post(account):
    post = PostService.create(account, request)
    return success_response('Post created', post.to_dict(), status_code=201)


# ── Feed endpoints ────────────────────────────────────────────────────────────

@posts_bp.route('/v1/posts/feed', methods=['GET'])
@lu_jwt_required
def get_feed(account):
    mode = request.args.get('mode', 'professional')
    page, per_page = _pagination()
    posts, total = PostService.get_feed(account, mode, page, per_page)
    return paginated_response(posts, total, page, per_page)


@posts_bp.route('/v1/posts/trending', methods=['GET'])
@lu_jwt_required
def get_trending(account):
    mode = request.args.get('mode', 'professional')
    page, per_page = _pagination()
    posts, total = PostService.get_trending(account, mode, page, per_page)
    return paginated_response(posts, total, page, per_page)


@posts_bp.route('/v1/posts/saved', methods=['GET'])
@lu_jwt_required
def get_saved(account):
    page, per_page = _pagination()
    posts, total = PostService.get_saved(account, page, per_page)
    return paginated_response(posts, total, page, per_page)


@posts_bp.route('/v1/posts/by/<account_id>', methods=['GET'])
@lu_jwt_required
def get_by_account(account, account_id):
    page, per_page = _pagination()
    posts, total = PostService.get_by_account(account.id, account_id, page, per_page)
    return paginated_response(posts, total, page, per_page)


# ── Single post CRUD ──────────────────────────────────────────────────────────

@posts_bp.route('/v1/posts/<post_id>', methods=['GET'])
@lu_jwt_required
def get_post(account, post_id):
    post = PostService.get_by_id(post_id)
    if not post:
        return error_response('Post not found', status_code=404)
    enriched = PostService._enrich([post], account.id)
    return success_response('OK', enriched[0])


@posts_bp.route('/v1/posts/<post_id>', methods=['PATCH'])
@lu_jwt_required
def update_post(account, post_id):
    post = PostService.get_by_id(post_id)
    if not post:
        return error_response('Post not found', status_code=404)
    if post.author_id != account.id:
        return error_response('Not authorised', status_code=403)
    data = request.get_json(silent=True) or {}
    updated = PostService.update(post, data)
    return success_response('Updated', updated.to_dict())


@posts_bp.route('/v1/posts/<post_id>', methods=['DELETE'])
@lu_jwt_required
def delete_post(account, post_id):
    post = PostService.get_by_id(post_id)
    if not post:
        return error_response('Post not found', status_code=404)
    if post.author_id != account.id and not account.is_admin:
        return error_response('Not authorised', status_code=403)
    PostService.delete(post)
    return success_response('Post deleted')


# ── Reactions ────────────────────────────────────────────────────────────────

@posts_bp.route('/v1/posts/<post_id>/like', methods=['POST'])
@lu_jwt_required
def toggle_like(account, post_id):
    post = PostService.get_by_id(post_id)
    if not post:
        return error_response('Post not found', status_code=404)
    data = request.get_json(silent=True) or {}
    result = PostService.toggle_like(post, account.id, data.get('reaction_type', 'like'))
    return success_response('OK', {'reaction': result, 'likes_count': post.likes_count})


@posts_bp.route('/v1/posts/<post_id>/likes', methods=['GET'])
@lu_jwt_required
def get_likers(account, post_id):
    page, per_page = _pagination()
    likes, total = PostService.get_likers(post_id, page, per_page)
    return paginated_response(likes, total, page, per_page)


# ── Save ─────────────────────────────────────────────────────────────────────

@posts_bp.route('/v1/posts/<post_id>/save', methods=['POST'])
@lu_jwt_required
def toggle_save(account, post_id):
    post = PostService.get_by_id(post_id)
    if not post:
        return error_response('Post not found', status_code=404)
    saved = PostService.toggle_save(post, account.id)
    return success_response('OK', {'saved': saved})


# ── View (silent) ─────────────────────────────────────────────────────────────

@posts_bp.route('/v1/posts/<post_id>/view', methods=['POST'])
@lu_jwt_required
def register_view(account, post_id):
    post = PostService.get_by_id(post_id)
    if not post:
        return error_response('Post not found', status_code=404)
    PostService.register_view(post)
    return success_response('OK')


# ── Reshare ───────────────────────────────────────────────────────────────────

@posts_bp.route('/v1/posts/<post_id>/share', methods=['POST'])
@lu_jwt_required
def share_post(account, post_id):
    post = PostService.get_by_id(post_id)
    if not post:
        return error_response('Post not found', status_code=404)
    data = request.get_json(silent=True) or {}
    shared = PostService.share(post, account, body=data.get('body'))
    return success_response('Reshared', shared.to_dict(), status_code=201)


# ── Comments ─────────────────────────────────────────────────────────────────

@posts_bp.route('/v1/posts/<post_id>/comments', methods=['GET'])
@lu_jwt_required
def get_comments(account, post_id):
    page, per_page = _pagination()
    comments, total = PostService.get_comments(post_id, account.id, page, per_page)
    return paginated_response(comments, total, page, per_page)


@posts_bp.route('/v1/posts/<post_id>/comments', methods=['POST'])
@lu_jwt_required
def add_comment(account, post_id):
    post = PostService.get_by_id(post_id)
    if not post:
        return error_response('Post not found', status_code=404)
    data = request.get_json(silent=True) or {}
    body = (data.get('body', '') or '').strip()
    if not body:
        return error_response('Comment body is required')
    comment = PostService.add_comment(post, account.id, body, data.get('parent_id'))
    return success_response('Comment added', comment.to_dict(), status_code=201)


@posts_bp.route('/v1/comments/<comment_id>', methods=['PATCH'])
@lu_jwt_required
def update_comment(account, comment_id):
    comment = PostComment.query.filter_by(id=comment_id).filter(
        PostComment.deleted_at.is_(None)
    ).first()
    if not comment:
        return error_response('Comment not found', status_code=404)
    if comment.author_id != account.id:
        return error_response('Not authorised', status_code=403)
    data = request.get_json(silent=True) or {}
    body = (data.get('body', '') or '').strip()
    if not body:
        return error_response('Comment body is required')
    return success_response('Updated', PostService.update_comment(comment, body).to_dict())


@posts_bp.route('/v1/comments/<comment_id>', methods=['DELETE'])
@lu_jwt_required
def delete_comment(account, comment_id):
    comment = PostComment.query.filter_by(id=comment_id).filter(
        PostComment.deleted_at.is_(None)
    ).first()
    if not comment:
        return error_response('Comment not found', status_code=404)
    if comment.author_id != account.id and not account.is_admin:
        return error_response('Not authorised', status_code=403)
    post = PostService.get_by_id(comment.post_id)
    PostService.delete_comment(comment, post)
    return success_response('Comment deleted')


@posts_bp.route('/v1/comments/<comment_id>/like', methods=['POST'])
@lu_jwt_required
def toggle_comment_like(account, comment_id):
    comment = PostComment.query.filter_by(id=comment_id).filter(
        PostComment.deleted_at.is_(None)
    ).first()
    if not comment:
        return error_response('Comment not found', status_code=404)
    liked = PostService.toggle_comment_like(comment, account.id)
    return success_response('OK', {'liked': liked, 'likes_count': comment.likes_count})


# ── Poll vote ─────────────────────────────────────────────────────────────────

@posts_bp.route('/v1/posts/<post_id>/poll/vote', methods=['POST'])
@lu_jwt_required
def vote_poll(account, post_id):
    post = PostService.get_by_id(post_id)
    if not post:
        return error_response('Post not found', status_code=404)
    data = request.get_json(silent=True) or {}
    option_id = data.get('option_id', '').strip()
    if not option_id:
        return error_response('option_id is required')
    options, err = PostService.vote_poll(post, account.id, option_id)
    if err and err != 'Already voted':
        return error_response(err)
    return success_response('Vote recorded', {'options': options, 'my_vote': option_id})
