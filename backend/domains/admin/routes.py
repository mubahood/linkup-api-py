"""
Admin v1 routes: /v1/admin/*
All endpoints require is_admin=1 on the calling account.
"""
from datetime import datetime, timedelta
from flask import Blueprint, request
from sqlalchemy import func, or_
from backend.models import db
from backend.domains.identity.models import Account
from backend.domains.safety.models import Report
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.utils.response import success_response, error_response, paginated_response
from backend.shared.utils.pagination import paginate_query

admin_v1_bp = Blueprint('v1_admin', __name__, url_prefix='/v1/admin')


@admin_v1_bp.route('/login', methods=['POST'])
def admin_login():
    """
    Admin console login. Accepts any of: phone, email, or handle + password.
    Returns a JWT access_token valid for the admin session.
    """
    from backend.domains.identity.service import issue_tokens
    data = request.get_json(silent=True) or {}

    identifier = (
        data.get('identifier') or
        data.get('phone') or
        data.get('email') or
        data.get('handle') or ''
    ).strip()
    password = (data.get('password') or '').strip()

    if not identifier or not password:
        return error_response('Identifier and password are required.', status_code=400)

    identifier_lower = identifier.lower()
    account = Account.query.filter(
        or_(
            Account.phone == identifier,
            Account.email == identifier_lower,
            Account.handle == identifier_lower,
        ),
        Account.deleted_at.is_(None),
    ).first()

    if not account:
        return error_response('No account found with those credentials.', status_code=401)

    if account.account_status != 'active':
        return error_response('This account is suspended or closed.', status_code=403)

    if not account.is_admin:
        return error_response('Admin access required.', status_code=403)

    if not account.check_password(password):
        return error_response('Invalid credentials.', status_code=401)

    tokens = issue_tokens(account)
    return success_response('Login successful.', {**account.to_dict(), **tokens})


def _admin_required(fn):
    """Decorator: require is_admin=1."""
    from functools import wraps

    @wraps(fn)
    @lu_jwt_required
    def wrapper(account, *args, **kwargs):
        if not account.is_admin:
            return error_response('Admin access required.', status_code=403)
        return fn(account, *args, **kwargs)
    return wrapper


# ─── Dashboard Stats ──────────────────────────────────────────────────────────

@admin_v1_bp.route('/events', methods=['GET'])
@_admin_required
def behavioral_events(account):
    """Inspect the behavioral event stream (T-API-053). Filter: ?verb=&account_id=&per_page="""
    from backend.shared.events.models import BehavioralEvent
    from backend.shared.utils.response import paginated_response
    q = BehavioralEvent.query
    verb = request.args.get('verb')
    acct = request.args.get('account_id')
    if verb:
        q = q.filter(BehavioralEvent.verb == verb)
    if acct:
        q = q.filter(BehavioralEvent.account_id == acct)
    page = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 50)), 200)
    total = q.count()
    rows = (q.order_by(BehavioralEvent.created_at.desc())
            .offset((page - 1) * per_page).limit(per_page).all())
    return paginated_response([e.to_dict() for e in rows], total, page, per_page, 'Events loaded.')


@admin_v1_bp.route('/stats', methods=['GET'])
@_admin_required
def stats(account):
    """Platform-wide stats snapshot."""
    from backend.domains.hubs.models import Hub, HubPost
    from backend.domains.jobs.models import Job
    from backend.domains.events.models import Event
    from backend.domains.sparks.models import Match
    from backend.domains.links.models import Link
    from backend.domains.notifications.models import Notification

    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    data = {
        'accounts': {
            'total': Account.query.filter(Account.deleted_at.is_(None)).count(),
            'active': Account.query.filter(
                Account.account_status == 'active',
                Account.deleted_at.is_(None)
            ).count(),
            'premium': Account.query.filter(Account.is_premium == 1).count(),
            'new_today': Account.query.filter(Account.created_at >= day_ago).count(),
            'new_this_week': Account.query.filter(Account.created_at >= week_ago).count(),
            'suspended': Account.query.filter(Account.account_status == 'suspended').count(),
        },
        'content': {
            'hubs': Hub.query.count(),
            'hub_posts': HubPost.query.filter(HubPost.deleted_at.is_(None)).count(),
            'jobs_open': Job.query.filter_by(is_open=1).count(),
            'events': Event.query.count(),
            'matches': Match.query.count(),
            'links': Link.query.filter_by(status='accepted').count(),
        },
        'moderation': {
            'pending_reports': Report.query.filter_by(status='pending').count(),
            'total_reports': Report.query.count(),
        },
    }
    return success_response('Stats loaded.', data)


# ─── Account Management ───────────────────────────────────────────────────────

@admin_v1_bp.route('/accounts', methods=['GET'])
@_admin_required
def list_accounts(account):
    """List all accounts with filters."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    q = request.args.get('q', '').strip()
    status = request.args.get('status', '')
    kyc_level = request.args.get('kyc_level', None, type=int)

    query = Account.query.filter(Account.deleted_at.is_(None))
    if q:
        query = query.filter(or_(
            Account.display_name.ilike(f'%{q}%'),
            Account.handle.ilike(f'%{q}%'),
            Account.phone.ilike(f'%{q}%'),
            Account.email.ilike(f'%{q}%'),
        ))
    if status:
        query = query.filter(Account.account_status == status)
    if kyc_level is not None:
        query = query.filter(Account.kyc_level == kyc_level)

    query = query.order_by(Account.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response(
        [a.to_dict() for a in items], total, page, per_page, 'Accounts loaded.'
    )


@admin_v1_bp.route('/accounts/<account_id>', methods=['GET'])
@_admin_required
def get_account(account, account_id):
    """Get a single account detail."""
    target = db.session.get(Account, account_id)
    if not target:
        return error_response('Account not found.', status_code=404)
    data = target.to_dict()
    # Attach report count
    data['report_count'] = Report.query.filter_by(target_account_id=account_id).count()
    return success_response('Account loaded.', data)


@admin_v1_bp.route('/accounts/<account_id>/status', methods=['PUT'])
@_admin_required
def set_account_status(account, account_id):
    """
    Set account status: active | suspended | closed.
    Cannot suspend or modify another admin unless you are the same admin.
    """
    if account_id == account.id:
        return error_response('You cannot change your own account status.')

    target = db.session.get(Account, account_id)
    if not target or target.deleted_at:
        return error_response('Account not found.', status_code=404)

    data = request.get_json(silent=True) or {}
    new_status = (data.get('status') or '').strip()
    reason = (data.get('reason') or '').strip()

    if new_status not in ('active', 'suspended', 'closed'):
        return error_response('status must be: active, suspended, or closed')

    if target.is_admin and new_status != 'active':
        return error_response('Cannot suspend another admin account.')

    target.account_status = new_status
    if new_status == 'closed':
        target.deleted_at = datetime.utcnow()
    db.session.commit()

    # In-app notification
    try:
        from backend.domains.notifications.service import create_notification
        msgs = {
            'suspended': ('Your account has been suspended',
                          reason or 'Your account has been suspended for violating our community guidelines.'),
            'active':    ('Your account has been reinstated', 'Your account is now active again. Welcome back!'),
            'closed':    ('Your account has been closed', reason or 'Your account has been permanently closed.'),
        }
        title, body = msgs[new_status]
        create_notification(
            account_id=account_id,
            notif_type=f'admin.account_{new_status}',
            title=title, body=body,
            data={'reason': reason}, action_url='/support',
        )
    except Exception:
        pass

    # Email notification
    if target.email:
        try:
            from backend.shared.email.service import send_account_status_email
            send_account_status_email(target.email, target.display_name, new_status, reason)
        except Exception:
            pass

    return success_response(f'Account status set to {new_status}.', target.to_dict())


@admin_v1_bp.route('/accounts/<account_id>/premium', methods=['PUT'])
@_admin_required
def set_premium(account, account_id):
    """Grant or revoke LinkUp+ premium status."""
    target = db.session.get(Account, account_id)
    if not target or target.deleted_at:
        return error_response('Account not found.', status_code=404)
    data = request.get_json(silent=True) or {}
    is_premium = bool(data.get('is_premium', True))
    target.is_premium = 1 if is_premium else 0
    db.session.commit()
    return success_response(
        f'Premium {"granted" if is_premium else "revoked"}.', target.to_dict()
    )


# ─── Report Management ────────────────────────────────────────────────────────

@admin_v1_bp.route('/reports', methods=['GET'])
@_admin_required
def list_reports(account):
    """List user reports with filters."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', 'pending')
    reason = request.args.get('reason', '')

    query = Report.query
    if status:
        query = query.filter(Report.status == status)
    if reason:
        query = query.filter(Report.reason == reason)
    query = query.order_by(Report.created_at.desc())

    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    result = []
    for r in items:
        d = r.to_dict()
        target = db.session.get(Account, r.target_account_id)
        reporter = db.session.get(Account, r.reporter_id)
        d['target'] = target.to_dict() if target else None
        d['reporter'] = {'id': reporter.id, 'display_name': reporter.display_name,
                         'handle': reporter.handle} if reporter else None
        result.append(d)
    return paginated_response(result, total, page, per_page, 'Reports loaded.')


@admin_v1_bp.route('/reports/<report_id>/resolve', methods=['PUT'])
@_admin_required
def resolve_report(account, report_id):
    """Resolve or dismiss a report."""
    report = db.session.get(Report, report_id)
    if not report:
        return error_response('Report not found.', status_code=404)
    data = request.get_json(silent=True) or {}
    action = (data.get('action') or '').strip()
    if action not in ('resolve', 'dismiss', 'escalate'):
        return error_response('action must be: resolve, dismiss, or escalate')
    status_map = {'resolve': 'resolved', 'dismiss': 'dismissed', 'escalate': 'escalated'}
    report.status = status_map[action]
    db.session.commit()
    return success_response(f'Report {report.status}.', report.to_dict())


# ─── Hub Management ───────────────────────────────────────────────────────────

@admin_v1_bp.route('/hubs', methods=['GET'])
@_admin_required
def list_hubs_admin(account):
    """Admin hub list — includes private hubs."""
    from backend.domains.hubs.models import Hub
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    q = request.args.get('q', '').strip()
    query = Hub.query
    if q:
        query = query.filter(Hub.name.ilike(f'%{q}%'))
    query = query.order_by(Hub.member_count.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([h.to_dict() for h in items], total, page, per_page, 'Hubs loaded.')
