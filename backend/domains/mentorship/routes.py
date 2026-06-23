"""
Mentorship routes: /v1/mentorship/*

Mentors list themselves, mentees browse and send requests.
Mentors accept/decline; accepted pairs can mark sessions complete.
"""
import uuid
from datetime import datetime
from flask import Blueprint, request
from backend.models import db
from backend.domains.mentorship.models import MentorProfile, MentorshipRequest
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.utils.response import success_response, error_response, paginated_response
from backend.shared.utils.pagination import paginate_query

mentorship_bp = Blueprint('v1_mentorship', __name__, url_prefix='/v1/mentorship')

VALID_MODES = {'online', 'in_person', 'both'}


# ─── Mentor Profiles ─────────────────────────────────────────────────────────

@mentorship_bp.route('/mentors', methods=['GET'])
@lu_jwt_required
def list_mentors(account):
    """
    Browse open mentor profiles.
    Filters: ?q= (headline/bio), ?mode=online|in_person|both, ?industry=text
    Ordered by session_count desc (experienced mentors first).
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    q = request.args.get('q', '').strip()
    mode = request.args.get('mode', '').strip()
    industry = request.args.get('industry', '').strip()

    from sqlalchemy import or_
    query = MentorProfile.query.filter_by(is_open=1)
    if q:
        query = query.filter(
            or_(
                MentorProfile.headline.ilike(f'%{q}%'),
                MentorProfile.bio.ilike(f'%{q}%'),
            )
        )
    if mode and mode in VALID_MODES:
        query = query.filter(MentorProfile.mentorship_mode == mode)

    # Exclude self from browse
    query = query.filter(MentorProfile.account_id != account.id)
    query = query.order_by(MentorProfile.session_count.desc(), MentorProfile.created_at.desc())

    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([m.to_dict() for m in items], total, page, per_page, 'Mentors loaded.')


@mentorship_bp.route('/mentors/me', methods=['GET'])
@lu_jwt_required
def my_mentor_profile(account):
    """Get my own mentor profile, or 404 if not set up."""
    profile = MentorProfile.query.filter_by(account_id=account.id).first()
    if not profile:
        return error_response('You have not set up a mentor profile.', status_code=404)
    return success_response('Mentor profile loaded.', profile.to_dict())


@mentorship_bp.route('/mentors/me', methods=['POST'])
@lu_jwt_required
def create_mentor_profile(account):
    """Create a mentor profile (must not already have one)."""
    if MentorProfile.query.filter_by(account_id=account.id).first():
        return error_response('You already have a mentor profile. Use PUT to update it.')

    data = request.get_json(silent=True) or {}
    headline = (data.get('headline') or '').strip()
    if not headline:
        return error_response('headline is required.')

    mode = data.get('mentorship_mode', 'both')
    if mode not in VALID_MODES:
        return error_response(f'mentorship_mode must be one of: {", ".join(VALID_MODES)}')

    capacity = int(data.get('capacity', 3))
    if not (1 <= capacity <= 10):
        return error_response('capacity must be between 1 and 10.')

    session_duration = int(data.get('session_duration', 60))
    if session_duration not in (30, 45, 60, 90, 120):
        return error_response('session_duration must be 30, 45, 60, 90, or 120 minutes.')

    profile = MentorProfile(
        id=str(uuid.uuid4()),
        account_id=account.id,
        headline=headline,
        bio=(data.get('bio') or '').strip() or None,
        skills=data.get('skills') or [],
        industries=data.get('industries') or [],
        mentorship_mode=mode,
        session_duration=session_duration,
        capacity=capacity,
        is_open=1,
    )
    db.session.add(profile)
    db.session.commit()
    return success_response('Mentor profile created.', profile.to_dict(), status_code=201)


@mentorship_bp.route('/mentors/me', methods=['PUT'])
@lu_jwt_required
def update_mentor_profile(account):
    """Update my mentor profile fields."""
    profile = MentorProfile.query.filter_by(account_id=account.id).first()
    if not profile:
        return error_response('No mentor profile found. Create one first.', status_code=404)

    data = request.get_json(silent=True) or {}

    for field in ['headline', 'bio']:
        if field in data:
            setattr(profile, field, (data[field] or '').strip() or None)

    for field in ['skills', 'industries']:
        if field in data and isinstance(data[field], list):
            setattr(profile, field, data[field])

    if 'mentorship_mode' in data:
        if data['mentorship_mode'] not in VALID_MODES:
            return error_response(f'mentorship_mode must be one of: {", ".join(VALID_MODES)}')
        profile.mentorship_mode = data['mentorship_mode']

    if 'session_duration' in data:
        dur = int(data['session_duration'])
        if dur not in (30, 45, 60, 90, 120):
            return error_response('session_duration must be 30, 45, 60, 90, or 120 minutes.')
        profile.session_duration = dur

    if 'capacity' in data:
        cap = int(data['capacity'])
        if not (1 <= cap <= 10):
            return error_response('capacity must be between 1 and 10.')
        profile.capacity = cap

    if 'is_open' in data:
        profile.is_open = 1 if data['is_open'] else 0

    db.session.commit()
    return success_response('Mentor profile updated.', profile.to_dict())


@mentorship_bp.route('/mentors/me', methods=['DELETE'])
@lu_jwt_required
def delete_mentor_profile(account):
    """Remove mentor profile (close to new requests first)."""
    profile = MentorProfile.query.filter_by(account_id=account.id).first()
    if not profile:
        return error_response('No mentor profile found.', status_code=404)
    # Check for pending requests
    pending = MentorshipRequest.query.filter_by(mentor_id=account.id, status='pending').count()
    if pending > 0:
        return error_response(
            f'You have {pending} pending request(s). Respond to them before deleting your profile.'
        )
    db.session.delete(profile)
    db.session.commit()
    return success_response('Mentor profile deleted.')


@mentorship_bp.route('/mentors/@<handle>', methods=['GET'])
@lu_jwt_required
def get_mentor_by_handle(account, handle):
    """Get a mentor profile by @handle."""
    from backend.domains.identity.models import Account
    normalized = handle.lower().replace('-', '_')
    target = Account.query.filter(
        Account.handle.ilike(normalized),
        Account.deleted_at.is_(None),
    ).first()
    if not target:
        return error_response('Account not found.', status_code=404)
    profile = MentorProfile.query.filter_by(account_id=target.id).first()
    if not profile:
        return error_response('This account is not offering mentorship.', status_code=404)
    return success_response('Mentor profile loaded.', profile.to_dict())


# ─── Mentorship Requests ──────────────────────────────────────────────────────

@mentorship_bp.route('/requests', methods=['POST'])
@lu_jwt_required
def send_request(account):
    """
    Send a mentorship request to a mentor.
    Body: { mentor_id, message, goals }
    """
    data = request.get_json(silent=True) or {}
    mentor_id = (data.get('mentor_id') or '').strip()
    message = (data.get('message') or '').strip()
    goals = (data.get('goals') or '').strip()

    if not mentor_id:
        return error_response('mentor_id is required.')
    if mentor_id == account.id:
        return error_response('You cannot request mentorship from yourself.')

    # Mentor must have an open profile
    mentor_profile = MentorProfile.query.filter_by(account_id=mentor_id, is_open=1).first()
    if not mentor_profile:
        return error_response('This mentor is not currently accepting requests.', status_code=404)

    # Check capacity: how many active mentees does this mentor have?
    active_count = MentorshipRequest.query.filter_by(
        mentor_id=mentor_id, status='accepted'
    ).count()
    if active_count >= mentor_profile.capacity:
        return error_response(
            f'This mentor is at full capacity ({mentor_profile.capacity} mentees).'
        )

    # No duplicate requests
    existing = MentorshipRequest.query.filter_by(
        mentee_id=account.id, mentor_id=mentor_id
    ).filter(MentorshipRequest.status.in_(['pending', 'accepted'])).first()
    if existing:
        return error_response(
            f'You already have a {existing.status} request with this mentor.'
        )

    req = MentorshipRequest(
        id=str(uuid.uuid4()),
        mentee_id=account.id,
        mentor_id=mentor_id,
        message=message or None,
        goals=goals or None,
    )
    db.session.add(req)
    db.session.commit()

    # In-app notification
    try:
        from backend.domains.notifications.service import create_notification
        create_notification(
            account_id=mentor_id,
            notif_type='mentorship.requested',
            title=f'{account.display_name} wants you as their mentor',
            body=message[:80] if message else f'New mentorship request for {mentor_profile.headline}',
            data={'request_id': req.id, 'mentee_id': account.id},
            action_url='/mentorship/requests',
        )
    except Exception:
        pass

    # Email notification to mentor
    from backend.domains.identity.models import Account as _Acct
    mentor_acct = db.session.get(_Acct, mentor_id)
    if mentor_acct and mentor_acct.email:
        try:
            from backend.shared.email.service import send_mentorship_email
            send_mentorship_email(
                to=mentor_acct.email,
                mentor_name=mentor_acct.display_name,
                mentee_name=account.display_name,
                message=message,
                goals=goals,
            )
        except Exception:
            pass

    return success_response('Mentorship request sent.', req.to_dict(), status_code=201)


@mentorship_bp.route('/requests/sent', methods=['GET'])
@lu_jwt_required
def sent_requests(account):
    """Requests I sent as a mentee."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', '')
    query = MentorshipRequest.query.filter_by(mentee_id=account.id)
    if status:
        query = query.filter(MentorshipRequest.status == status)
    query = query.order_by(MentorshipRequest.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([r.to_dict() for r in items], total, page, per_page, 'Sent requests loaded.')


@mentorship_bp.route('/requests/received', methods=['GET'])
@lu_jwt_required
def received_requests(account):
    """Requests I received as a mentor."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', '')
    query = MentorshipRequest.query.filter_by(mentor_id=account.id)
    if status:
        query = query.filter(MentorshipRequest.status == status)
    query = query.order_by(MentorshipRequest.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([r.to_dict() for r in items], total, page, per_page, 'Received requests loaded.')


@mentorship_bp.route('/requests/<request_id>/respond', methods=['POST'])
@lu_jwt_required
def respond_to_request(account, request_id):
    """
    Accept or decline a mentorship request (mentor only).
    Body: { action: "accept" | "decline" }
    """
    req = MentorshipRequest.query.filter_by(
        id=request_id, mentor_id=account.id
    ).first()
    if not req:
        return error_response('Request not found.', status_code=404)
    if req.status != 'pending':
        return error_response(f'This request is already {req.status}.')

    data = request.get_json(silent=True) or {}
    action = (data.get('action') or '').lower().strip()
    if action not in ('accept', 'decline'):
        return error_response('action must be: accept or decline')

    req.status = 'accepted' if action == 'accept' else 'declined'
    req.responded_at = datetime.utcnow()
    db.session.commit()

    # Notify mentee
    try:
        from backend.domains.notifications.service import create_notification
        create_notification(
            account_id=req.mentee_id,
            notif_type=f'mentorship.{req.status}',
            title=f'{account.display_name} {req.status} your mentorship request',
            body='Check your mentorship dashboard for next steps.' if req.status == 'accepted'
            else 'They may not have capacity right now. Try other mentors.',
            data={'request_id': request_id, 'mentor_id': account.id},
            action_url='/mentorship',
        )
    except Exception:
        pass

    return success_response(f'Request {req.status}.', req.to_dict())


@mentorship_bp.route('/requests/<request_id>/complete', methods=['POST'])
@lu_jwt_required
def complete_request(account, request_id):
    """
    Mark a mentorship relationship as complete (either party can do this).
    Records the outcome for the mentor's session_count.
    """
    from sqlalchemy import or_
    req = MentorshipRequest.query.filter(
        MentorshipRequest.id == request_id,
        or_(
            MentorshipRequest.mentee_id == account.id,
            MentorshipRequest.mentor_id == account.id,
        ),
        MentorshipRequest.status == 'accepted',
    ).first()
    if not req:
        return error_response('Active mentorship request not found.', status_code=404)

    req.status = 'completed'
    req.completed_at = datetime.utcnow()

    # Increment mentor's session count
    mentor_profile = MentorProfile.query.filter_by(account_id=req.mentor_id).first()
    if mentor_profile:
        mentor_profile.session_count = (mentor_profile.session_count or 0) + 1

    db.session.commit()
    return success_response('Mentorship marked as complete.', req.to_dict())


@mentorship_bp.route('/requests/<request_id>/withdraw', methods=['POST'])
@lu_jwt_required
def withdraw_request(account, request_id):
    """Mentee can withdraw a pending request."""
    req = MentorshipRequest.query.filter_by(
        id=request_id, mentee_id=account.id, status='pending'
    ).first()
    if not req:
        return error_response('Pending request not found.', status_code=404)
    req.status = 'withdrawn'
    db.session.commit()
    return success_response('Request withdrawn.', req.to_dict())
