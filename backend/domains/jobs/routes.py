"""
Jobs routes: /v1/jobs/*

Endpoints:
  GET  /v1/jobs                         — public feed
  POST /v1/jobs                         — post a new job
  GET  /v1/jobs/mine                    — my posted jobs
  GET  /v1/jobs/saved                   — saved jobs
  GET  /v1/jobs/applications            — my applications (as applicant)
  GET  /v1/jobs/<id>                    — job detail (increments view_count)
  PUT  /v1/jobs/<id>                    — update job (poster only)
  DELETE /v1/jobs/<id>                  — delete job (poster only)
  POST /v1/jobs/<id>/close              — close job (poster only)
  POST /v1/jobs/<id>/reopen             — reopen job (poster only)
  GET  /v1/jobs/<id>/stats              — job stats — poster only
  GET  /v1/jobs/<id>/applicants         — applicant list (poster only)
  POST /v1/jobs/<id>/apply              — submit application
  POST /v1/jobs/<id>/withdraw           — withdraw my application
  POST /v1/jobs/<id>/save               — toggle save/unsave
  POST /v1/jobs/<id>/contact-poster     — create/get thread with poster
  POST /v1/jobs/<id>/referral           — request referral
  GET  /v1/jobs/referrals/sent          — sent referral requests
  GET  /v1/jobs/referrals/received      — received referral requests
  POST /v1/jobs/referrals/<id>/respond  — respond to referral
  PUT  /v1/jobs/applications/<id>/status — recruiter updates status
"""
import uuid
from flask import Blueprint, request
from backend.models import db
from backend.domains.jobs.models import Job, Application, SavedJob
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.idempotency import idempotent
from backend.shared.utils.response import success_response, error_response, paginated_response
from backend.shared.utils.pagination import paginate_query

jobs_bp = Blueprint('v1_jobs', __name__, url_prefix='/v1/jobs')

VALID_STATUSES = {'applied', 'shortlisted', 'interview', 'hired', 'rejected', 'withdrawn'}


# ── Helper ────────────────────────────────────────────────────────────────────

def _enrich(job: Job, account_id: str, include_count: bool = False) -> dict:
    saved       = SavedJob.query.filter_by(job_id=job.id, account_id=account_id).first()
    application = Application.query.filter_by(job_id=job.id, applicant_id=account_id).first()
    return job.to_dict(
        is_saved=bool(saved),
        application=application,
        include_application_count=include_count,
    )


# ── Feed ──────────────────────────────────────────────────────────────────────

@jobs_bp.route('', methods=['GET'])
@lu_jwt_required
def jobs_feed(account):
    """
    GET /v1/jobs
    ?q=              keyword search (title + description)
    ?employment_type= full_time | part_time | contract | internship
    ?seniority=       entry | mid | senior | lead
    ?work_mode=       onsite | remote | hybrid
    ?referral_open=   1 — only jobs accepting referrals
    ?per_page=
    ?page=
    """
    page            = request.args.get('page',            1,  type=int)
    per_page        = request.args.get('per_page',       20,  type=int)
    q               = request.args.get('q',              '').strip()
    employment_type = request.args.get('employment_type','').strip()
    seniority       = request.args.get('seniority',      '').strip()
    work_mode       = request.args.get('work_mode',      '').strip()
    referral_only   = request.args.get('referral_open',  '').lower() == '1'

    query = Job.query.filter_by(is_open=1)
    if q:
        query = query.filter(
            (Job.title.ilike(f'%{q}%')) | (Job.description.ilike(f'%{q}%'))
        )
    if employment_type:
        query = query.filter(Job.employment_type == employment_type)
    if seniority:
        query = query.filter(Job.seniority == seniority)
    if work_mode:
        query = query.filter(Job.work_mode == work_mode)
    if referral_only:
        query = query.filter(Job.referral_open == 1)

    query = query.order_by(Job.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response(
        [_enrich(j, account.id) for j in items],
        total, page, per_page, 'Jobs loaded.',
    )


# ── Mine ──────────────────────────────────────────────────────────────────────

@jobs_bp.route('/mine', methods=['GET'])
@lu_jwt_required
def my_jobs(account):
    """My posted jobs — includes application counts and view counts."""
    page     = request.args.get('page',     1,  type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status   = request.args.get('status',   '')   # open | closed
    query    = Job.query.filter_by(posted_by=account.id)
    if status == 'open':
        query = query.filter(Job.is_open == 1)
    elif status == 'closed':
        query = query.filter(Job.is_open == 0)
    query = query.order_by(Job.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response(
        [_enrich(j, account.id, include_count=True) for j in items],
        total, page, per_page, 'My jobs loaded.',
    )


# ── Saved ─────────────────────────────────────────────────────────────────────

@jobs_bp.route('/saved', methods=['GET'])
@lu_jwt_required
def saved_jobs(account):
    page     = request.args.get('page',     1,  type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = (
        db.session.query(Job)
        .join(SavedJob, SavedJob.job_id == Job.id)
        .filter(SavedJob.account_id == account.id)
        .order_by(SavedJob.created_at.desc())
    )
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response(
        [_enrich(j, account.id) for j in items],
        total, page, per_page, 'Saved jobs loaded.',
    )


# ── Personalised "For You" feed ───────────────────────────────────────────────

@jobs_bp.route('/for-you', methods=['GET'])
@lu_jwt_required
def jobs_for_you(account):
    """
    GET /v1/jobs/for-you
    Returns top N open jobs ranked by relevance to the authenticated user.
    Uses: interest tag overlap, seniority match, location proximity, recency,
          and referral bonus.
    ?limit=8   (max 20)

    Each item extends the standard job dict with:
      match_pct    int   1–99
      match_reason str   e.g. "4 matching skills"
    """
    limit = min(request.args.get('limit', 8, type=int), 20)
    from backend.domains.jobs.service import get_jobs_for_you
    jobs = get_jobs_for_you(account.id, limit=limit)
    return success_response('Jobs for you loaded.', jobs)


# ── My applications (as job seeker) ──────────────────────────────────────────

@jobs_bp.route('/applications', methods=['GET'])
@lu_jwt_required
def my_applications(account):
    page     = request.args.get('page',     1,  type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status   = request.args.get('status',   '').strip()

    query = Application.query.filter_by(applicant_id=account.id)
    if status:
        query = query.filter(Application.status == status)
    query = query.order_by(Application.created_at.desc())

    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    result = []
    for app in items:
        job = db.session.get(Job, app.job_id)
        entry = app.to_dict()
        entry['job'] = _enrich(job, account.id) if job else None
        result.append(entry)
    return paginated_response(result, total, page, per_page, 'My applications loaded.')


# ── Post job ──────────────────────────────────────────────────────────────────

@jobs_bp.route('', methods=['POST'])
@lu_jwt_required
def post_job(account):
    """
    POST /v1/jobs
    Body: { title, description, requirements[], org_name, org_id,
            location_text, location_id, work_mode, employment_type,
            seniority, salary_min, salary_max, currency, skills[],
            referral_open, expires_at }
    """
    data  = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    if not title:
        return error_response('Job title is required.')

    job = Job(
        id              = str(uuid.uuid4()),
        posted_by       = account.id,
        title           = title,
        description     = data.get('description'),
        requirements    = data.get('requirements'),
        org_id          = data.get('org_id'),
        org_name        = (data.get('org_name') or '').strip() or None,
        location_id     = data.get('location_id'),
        location_text   = (data.get('location_text') or '').strip() or None,
        work_mode       = data.get('work_mode', 'onsite'),
        employment_type = data.get('employment_type', 'full_time'),
        seniority       = data.get('seniority', 'entry'),
        salary_min      = data.get('salary_min'),
        salary_max      = data.get('salary_max'),
        currency        = data.get('currency', 'UGX'),
        skills          = data.get('skills'),
        referral_open   = int(bool(data.get('referral_open', False))),
        expires_at      = data.get('expires_at'),
    )
    db.session.add(job)
    db.session.commit()
    return success_response('Job posted.', _enrich(job, account.id, include_count=True), status_code=201)


# ── Get job detail ────────────────────────────────────────────────────────────

@jobs_bp.route('/<job_id>', methods=['GET'])
@lu_jwt_required
def get_job(account, job_id):
    job = db.session.get(Job, job_id)
    if not job:
        return error_response('Job not found.', status_code=404)
    # Increment view count (skip poster's own views)
    if job.posted_by != account.id:
        try:
            job.view_count = (job.view_count or 0) + 1
            db.session.commit()
        except Exception:
            db.session.rollback()
    return success_response('Job loaded.', _enrich(job, account.id, include_count=True))


# ── Update job ────────────────────────────────────────────────────────────────

@jobs_bp.route('/<job_id>', methods=['PUT'])
@lu_jwt_required
def update_job(account, job_id):
    job = db.session.get(Job, job_id)
    if not job:
        return error_response('Job not found.', status_code=404)
    if job.posted_by != account.id:
        return error_response('Only the job poster can update this listing.', status_code=403)
    data = request.get_json(silent=True) or {}
    editable = [
        'title', 'description', 'requirements', 'org_name', 'location_text',
        'work_mode', 'employment_type', 'seniority', 'salary_min', 'salary_max',
        'currency', 'skills', 'expires_at',
    ]
    for field in editable:
        if field in data:
            setattr(job, field, data[field])
    if 'referral_open' in data:
        job.referral_open = int(bool(data['referral_open']))
    db.session.commit()
    return success_response('Job updated.', _enrich(job, account.id, include_count=True))


# ── Delete job ────────────────────────────────────────────────────────────────

@jobs_bp.route('/<job_id>', methods=['DELETE'])
@lu_jwt_required
def delete_job(account, job_id):
    """Permanently delete a job — poster only. Also removes all applications."""
    job = db.session.get(Job, job_id)
    if not job:
        return error_response('Job not found.', status_code=404)
    if job.posted_by != account.id:
        return error_response('Only the job poster can delete this listing.', status_code=403)
    db.session.delete(job)
    db.session.commit()
    return success_response('Job deleted.')


# ── Close / Reopen ────────────────────────────────────────────────────────────

@jobs_bp.route('/<job_id>/close', methods=['POST'])
@lu_jwt_required
def close_job(account, job_id):
    job = db.session.get(Job, job_id)
    if not job:
        return error_response('Job not found.', status_code=404)
    if job.posted_by != account.id:
        return error_response('Only the job poster can close this listing.', status_code=403)
    job.is_open = 0
    db.session.commit()
    return success_response('Job closed.', _enrich(job, account.id, include_count=True))


@jobs_bp.route('/<job_id>/reopen', methods=['POST'])
@lu_jwt_required
def reopen_job(account, job_id):
    job = db.session.get(Job, job_id)
    if not job:
        return error_response('Job not found.', status_code=404)
    if job.posted_by != account.id:
        return error_response('Only the job poster can reopen this listing.', status_code=403)
    job.is_open = 1
    db.session.commit()
    return success_response('Job reopened.', _enrich(job, account.id, include_count=True))


# ── Job stats (poster only) ───────────────────────────────────────────────────

@jobs_bp.route('/<job_id>/stats', methods=['GET'])
@lu_jwt_required
def job_stats(account, job_id):
    """
    GET /v1/jobs/<id>/stats — poster only.
    Returns application breakdown by status + view count.
    """
    job = db.session.get(Job, job_id)
    if not job:
        return error_response('Job not found.', status_code=404)
    if job.posted_by != account.id:
        return error_response('Only the job poster can view stats.', status_code=403)

    apps = Application.query.filter_by(job_id=job_id).all()
    by_status = {}
    for a in apps:
        by_status[a.status] = by_status.get(a.status, 0) + 1

    return success_response('Stats loaded.', {
        'total_applications': len(apps),
        'by_status':          by_status,
        'view_count':         job.view_count or 0,
        'is_open':            bool(job.is_open),
    })


# ── Applicants list (poster only) ─────────────────────────────────────────────

@jobs_bp.route('/<job_id>/applicants', methods=['GET'])
@lu_jwt_required
def job_applicants(account, job_id):
    job = db.session.get(Job, job_id)
    if not job:
        return error_response('Job not found.', status_code=404)
    if job.posted_by != account.id:
        return error_response('Only the job poster can view applicants.', status_code=403)

    page     = request.args.get('page',     1,  type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status   = request.args.get('status',   '').strip()

    query = Application.query.filter_by(job_id=job_id)
    if status:
        query = query.filter(Application.status == status)
    query = query.order_by(Application.created_at.asc())

    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response(
        [a.to_dict() for a in items],
        total, page, per_page, 'Applicants loaded.',
    )


# ── Apply ─────────────────────────────────────────────────────────────────────

@jobs_bp.route('/<job_id>/apply', methods=['POST'])
@lu_jwt_required
@idempotent
def apply_job(account, job_id):
    """
    POST /v1/jobs/<id>/apply
    Body: { cover_note (optional), referred_by (optional account_id) }
    """
    job = db.session.get(Job, job_id)
    if not job:
        return error_response('Job not found.', status_code=404)
    if not job.is_open:
        return error_response('This job is no longer accepting applications.')
    if job.posted_by == account.id:
        return error_response('You cannot apply to your own job posting.')

    existing = Application.query.filter_by(job_id=job_id, applicant_id=account.id).first()
    if existing:
        if existing.status == 'withdrawn':
            # Allow re-application after withdrawal
            existing.status = 'applied'
            existing.cover_note = request.get_json(silent=True, force=True).get('cover_note') or existing.cover_note
            db.session.commit()
            return success_response('Application resubmitted.', existing.to_dict())
        return error_response('You have already applied for this job.')

    data = request.get_json(silent=True) or {}
    application = Application(
        id           = str(uuid.uuid4()),
        job_id       = job_id,
        applicant_id = account.id,
        cover_note   = (data.get('cover_note') or '').strip() or None,
        referred_by  = data.get('referred_by'),
    )
    db.session.add(application)
    db.session.commit()

    from backend.shared.events.emit import emit
    emit('job.apply', account_id=account.id, object_type='job', object_id=job_id)

    # Notify the job poster
    try:
        from backend.domains.notifications.service import create_notification
        create_notification(
            account_id  = job.posted_by,
            notif_type  = 'job.application_received',
            title       = f'New application for {job.title}',
            body        = f'{account.display_name} applied for your job posting.',
            data        = {'job_id': job_id, 'application_id': application.id},
            action_url  = f'/jobs/{job_id}/applicants',
        )
    except Exception:
        pass

    return success_response('Application submitted.', application.to_dict(), status_code=201)


# ── Withdraw application ──────────────────────────────────────────────────────

@jobs_bp.route('/<job_id>/withdraw', methods=['POST'])
@lu_jwt_required
def withdraw_application(account, job_id):
    """Withdraw my application (sets status = withdrawn)."""
    app_rec = Application.query.filter_by(job_id=job_id, applicant_id=account.id).first()
    if not app_rec:
        return error_response('Application not found.', status_code=404)
    if app_rec.status in ('hired', 'rejected'):
        return error_response(f'Cannot withdraw an application that is already {app_rec.status}.')
    app_rec.status = 'withdrawn'
    db.session.commit()
    return success_response('Application withdrawn.', app_rec.to_dict())


# ── Save / Unsave ─────────────────────────────────────────────────────────────

@jobs_bp.route('/<job_id>/save', methods=['POST'])
@lu_jwt_required
def save_job(account, job_id):
    """Toggle save/unsave. Returns { saved: bool }."""
    job = db.session.get(Job, job_id)
    if not job:
        return error_response('Job not found.', status_code=404)
    saved = SavedJob.query.filter_by(job_id=job_id, account_id=account.id).first()
    if saved:
        db.session.delete(saved)
        db.session.commit()
        return success_response('Job unsaved.', {'saved': False})
    saved = SavedJob(id=str(uuid.uuid4()), job_id=job_id, account_id=account.id)
    db.session.add(saved)
    db.session.commit()
    return success_response('Job saved.', {'saved': True})


# ── Contact poster ────────────────────────────────────────────────────────────

@jobs_bp.route('/<job_id>/contact-poster', methods=['POST'])
@lu_jwt_required
def contact_poster(account, job_id):
    """
    POST /v1/jobs/<id>/contact-poster
    Creates or returns an existing direct thread with the job poster.
    Returns the thread data so the mobile client can navigate to the chat screen.
    Body: { message (optional) — pre-fill a first message }
    """
    job = db.session.get(Job, job_id)
    if not job:
        return error_response('Job not found.', status_code=404)
    if job.posted_by == account.id:
        return error_response('You cannot contact yourself.')

    from backend.domains.chat.service import get_or_create_direct_thread
    from backend.domains.chat.models import Thread, ThreadParticipant, Message
    from backend.domains.identity.models import Account as Acct

    thread = get_or_create_direct_thread(account.id, job.posted_by, mode='professional')

    # Send an optional opening message
    data    = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    if message:
        from datetime import datetime as _dt
        now = _dt.utcnow()
        msg = Message(
            id         = str(uuid.uuid4()),
            thread_id  = thread.id,
            sender_id  = account.id,
            body       = message,
            type       = 'text',
            created_at = now,
        )
        db.session.add(msg)
        thread.last_message_at = now
        db.session.commit()

    # Enrich thread for the client
    participants = ThreadParticipant.query.filter_by(thread_id=thread.id).all()
    other_parts  = [p for p in participants if p.account_id != account.id]
    other_acct   = db.session.get(Acct, job.posted_by) if other_parts else None

    thread_data = thread.to_dict(account.id, None, 0)
    thread_data['display_name']    = other_acct.display_name if other_acct else job.org_name or 'Poster'
    thread_data['avatar']          = other_acct.avatar if other_acct else None
    thread_data['other_participant'] = other_acct.to_dict() if other_acct else None

    return success_response('Thread ready.', thread_data)


# ── Update application status (recruiter) ─────────────────────────────────────

@jobs_bp.route('/applications/<application_id>/status', methods=['PUT'])
@lu_jwt_required
def update_application_status(account, application_id):
    """
    PUT /v1/jobs/applications/<id>/status
    Body: { status: shortlisted | interview | hired | rejected }
    Poster only.
    """
    app_rec = db.session.get(Application, application_id)
    if not app_rec:
        return error_response('Application not found.', status_code=404)

    job = db.session.get(Job, app_rec.job_id)
    if not job or job.posted_by != account.id:
        return error_response('Only the job poster can update application status.', status_code=403)

    data       = request.get_json(silent=True) or {}
    new_status = (data.get('status') or '').strip()
    ALLOWED    = {'shortlisted', 'interview', 'hired', 'rejected', 'applied'}
    if new_status not in ALLOWED:
        return error_response(f'status must be one of: {", ".join(sorted(ALLOWED))}')

    old_status       = app_rec.status
    app_rec.status   = new_status
    db.session.commit()

    if new_status != old_status:
        _notify_applicant_status(app_rec, job, account, new_status)

    return success_response('Application status updated.', app_rec.to_dict())


def _notify_applicant_status(app_rec, job, updater, new_status):
    """Send in-app + email notification to applicant on status change."""
    msgs = {
        'shortlisted': (
            f'You were shortlisted for {job.title}',
            'Congratulations! You\'ve been shortlisted.',
        ),
        'interview': (
            f'Interview invitation — {job.title}',
            'You\'ve been invited to interview. Check your messages for details.',
        ),
        'hired': (
            f'You got the job! — {job.title}',
            'Congratulations! Your application was successful.',
        ),
        'rejected': (
            f'Application update — {job.title}',
            'Thank you for applying. The position has been filled.',
        ),
    }
    if new_status not in msgs:
        return
    title, body = msgs[new_status]
    try:
        from backend.domains.notifications.service import create_notification
        create_notification(
            account_id = app_rec.applicant_id,
            notif_type = 'job.application_updated',
            title      = title,
            body       = body,
            data       = {'job_id': job.id, 'application_id': app_rec.id, 'status': new_status},
            action_url = f'/jobs/{job.id}',
        )
    except Exception:
        pass
    try:
        from backend.domains.identity.models import Account as Acct
        from backend.models import db as _db
        applicant = _db.session.get(Acct, app_rec.applicant_id)
        if applicant and applicant.email:
            from backend.shared.email.service import send_application_status_email
            send_application_status_email(
                to=applicant.email,
                name=applicant.display_name,
                job_title=job.title,
                status=new_status,
            )
    except Exception:
        pass


# ── Referral endpoints (unchanged from previous implementation) ────────────────

@jobs_bp.route('/<job_id>/referral', methods=['POST'])
@lu_jwt_required
def request_referral(account, job_id):
    from backend.domains.jobs.referral_models import JobReferral
    from backend.domains.links.models import Link
    from sqlalchemy import or_ as _or

    job = db.session.get(Job, job_id)
    if not job:
        return error_response('Job not found.', status_code=404)
    if not job.referral_open:
        return error_response('This job does not accept referral requests.')

    data        = request.get_json(silent=True) or {}
    referrer_id = (data.get('referrer_id') or '').strip()
    message     = (data.get('message') or '').strip()

    if not referrer_id:
        return error_response('referrer_id is required.')
    if referrer_id == account.id:
        return error_response('You cannot request a referral from yourself.')

    link = Link.query.filter(
        _or(
            (Link.requester_id == account.id) & (Link.addressee_id == referrer_id),
            (Link.requester_id == referrer_id) & (Link.addressee_id == account.id),
        ),
        Link.status == 'accepted',
    ).first()
    if not link:
        return error_response('You can only request referrals from your direct connections.')

    existing = JobReferral.query.filter_by(
        job_id=job_id, requester_id=account.id, referrer_id=referrer_id
    ).first()
    if existing:
        return error_response('You already requested a referral from this person for this job.')

    referral = JobReferral(
        id          = str(uuid.uuid4()),
        job_id      = job_id,
        requester_id= account.id,
        referrer_id = referrer_id,
        message     = message,
    )
    db.session.add(referral)
    db.session.commit()

    try:
        from backend.domains.notifications.service import create_notification
        create_notification(
            account_id  = referrer_id,
            notif_type  = 'job.referral_requested',
            title       = f'{account.display_name} is asking for a referral',
            body        = f'For: {job.title}. {message[:60]}' if message else f'For: {job.title}',
            data        = {'referral_id': referral.id, 'job_id': job_id},
            action_url  = f'/jobs/{job_id}',
        )
    except Exception:
        pass

    return success_response('Referral request sent.', referral.to_dict(), status_code=201)


@jobs_bp.route('/referrals/sent', methods=['GET'])
@lu_jwt_required
def sent_referrals(account):
    from backend.domains.jobs.referral_models import JobReferral
    page     = request.args.get('page',     1,  type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status   = request.args.get('status',   '').strip()
    query    = JobReferral.query.filter_by(requester_id=account.id)
    if status:
        query = query.filter(JobReferral.status == status)
    query = query.order_by(JobReferral.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    result = []
    for r in items:
        d   = r.to_dict()
        job = db.session.get(Job, r.job_id)
        d['job'] = {'id': job.id, 'title': job.title, 'org_name': job.org_name} if job else None
        result.append(d)
    return paginated_response(result, total, page, per_page, 'Sent referrals loaded.')


@jobs_bp.route('/referrals/received', methods=['GET'])
@lu_jwt_required
def received_referrals(account):
    from backend.domains.jobs.referral_models import JobReferral
    page     = request.args.get('page',     1,  type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status   = request.args.get('status',   '').strip()
    query    = JobReferral.query.filter_by(referrer_id=account.id)
    if status:
        query = query.filter(JobReferral.status == status)
    query = query.order_by(JobReferral.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([r.to_dict() for r in items], total, page, per_page, 'Referrals loaded.')


@jobs_bp.route('/referrals/<referral_id>/respond', methods=['POST'])
@lu_jwt_required
def respond_referral(account, referral_id):
    from backend.domains.jobs.referral_models import JobReferral
    from datetime import datetime
    referral = JobReferral.query.filter_by(id=referral_id, referrer_id=account.id).first()
    if not referral:
        return error_response('Referral request not found.', status_code=404)
    if referral.status != 'pending':
        return error_response(f'Referral already {referral.status}.')
    data   = request.get_json(silent=True) or {}
    action = data.get('action', '').lower()
    if action not in ('accept', 'decline', 'refer'):
        return error_response('action must be: accept, decline, or refer')
    referral.status       = {'accept': 'accepted', 'decline': 'declined', 'refer': 'referred'}[action]
    referral.responded_at = datetime.utcnow()
    db.session.commit()
    try:
        from backend.domains.notifications.service import create_notification
        job = db.session.get(Job, referral.job_id)
        create_notification(
            account_id  = referral.requester_id,
            notif_type  = 'job.referral_responded',
            title       = f'{account.display_name} {referral.status} your referral',
            body        = f'For: {job.title if job else "job"}',
            data        = {'referral_id': referral_id, 'status': referral.status},
            action_url  = f'/jobs/{referral.job_id}',
        )
    except Exception:
        pass
    return success_response(f'Referral {referral.status}.', referral.to_dict())
