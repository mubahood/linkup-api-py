"""
Jobs routes: /v1/jobs/*
"""
import uuid
from flask import Blueprint, request
from backend.models import db
from backend.domains.jobs.models import Job, Application, SavedJob
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.utils.response import success_response, error_response, paginated_response
from backend.shared.utils.pagination import paginate_query

jobs_bp = Blueprint('v1_jobs', __name__, url_prefix='/v1/jobs')


def _enrich_job(job: Job, account_id: str) -> dict:
    saved = SavedJob.query.filter_by(job_id=job.id, account_id=account_id).first()
    application = Application.query.filter_by(job_id=job.id, applicant_id=account_id).first()
    return job.to_dict(is_saved=bool(saved), application=application)


@jobs_bp.route('', methods=['GET'])
@lu_jwt_required
def jobs_feed(account):
    """Jobs feed filtered by query params."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    q = request.args.get('q', '')
    employment_type = request.args.get('employment_type', '')
    seniority = request.args.get('seniority', '')

    query = Job.query.filter_by(is_open=1)
    if q:
        query = query.filter(
            (Job.title.ilike(f'%{q}%')) | (Job.description.ilike(f'%{q}%'))
        )
    if employment_type:
        query = query.filter(Job.employment_type == employment_type)
    if seniority:
        query = query.filter(Job.seniority == seniority)
    query = query.order_by(Job.created_at.desc())

    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([_enrich_job(j, account.id) for j in items], total, page, per_page, 'Jobs loaded.')


@jobs_bp.route('/mine', methods=['GET'])
@lu_jwt_required
def my_jobs(account):
    """Jobs I posted."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = Job.query.filter_by(posted_by=account.id).order_by(Job.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([_enrich_job(j, account.id) for j in items], total, page, per_page, 'My jobs loaded.')


@jobs_bp.route('', methods=['POST'])
@lu_jwt_required
def post_job(account):
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    if not title:
        return error_response('Job title is required.')
    job = Job(
        id=str(uuid.uuid4()),
        posted_by=account.id,
        title=title,
        description=data.get('description'),
        org_id=data.get('org_id'),
        org_name=data.get('org_name'),
        location_id=data.get('location_id'),
        location_text=data.get('location_text'),
        employment_type=data.get('employment_type', 'full_time'),
        seniority=data.get('seniority', 'entry'),
        salary_min=data.get('salary_min'),
        salary_max=data.get('salary_max'),
        currency=data.get('currency', 'UGX'),
        skills=data.get('skills'),
        referral_open=int(data.get('referral_open', 0)),
        expires_at=data.get('expires_at'),
    )
    db.session.add(job)
    db.session.commit()
    return success_response('Job posted.', job.to_dict(), status_code=201)


@jobs_bp.route('/<job_id>', methods=['GET'])
@lu_jwt_required
def get_job(account, job_id):
    job = Job.query.get(job_id)
    if not job:
        return error_response('Job not found.', status_code=404)
    return success_response('Job loaded.', _enrich_job(job, account.id))


@jobs_bp.route('/<job_id>', methods=['PUT'])
@lu_jwt_required
def update_job(account, job_id):
    """Update a job posting — poster only."""
    job = Job.query.get(job_id)
    if not job:
        return error_response('Job not found.', status_code=404)
    if job.posted_by != account.id:
        return error_response('Only the job poster can update this listing.', status_code=403)
    data = request.get_json(silent=True) or {}
    for field in ['title', 'description', 'org_name', 'location_text', 'employment_type',
                  'seniority', 'salary_min', 'salary_max', 'currency', 'skills', 'expires_at']:
        if field in data:
            setattr(job, field, data[field])
    if 'referral_open' in data:
        job.referral_open = int(data['referral_open'])
    db.session.commit()
    return success_response('Job updated.', _enrich_job(job, account.id))


@jobs_bp.route('/<job_id>/close', methods=['POST'])
@lu_jwt_required
def close_job(account, job_id):
    """Close a job — poster only. Sets is_open=0."""
    job = Job.query.get(job_id)
    if not job:
        return error_response('Job not found.', status_code=404)
    if job.posted_by != account.id:
        return error_response('Only the job poster can close this listing.', status_code=403)
    job.is_open = 0
    db.session.commit()
    return success_response('Job closed.', _enrich_job(job, account.id))


@jobs_bp.route('/<job_id>/applicants', methods=['GET'])
@lu_jwt_required
def job_applicants(account, job_id):
    """List applicants for a job — poster only."""
    job = Job.query.get(job_id)
    if not job:
        return error_response('Job not found.', status_code=404)
    if job.posted_by != account.id:
        return error_response('Only the job poster can view applicants.', status_code=403)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = Application.query.filter_by(job_id=job_id).order_by(Application.created_at.asc())
    from backend.shared.utils.pagination import paginate_query
    from backend.shared.utils.response import paginated_response
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    result = []
    for app in items:
        from backend.domains.identity.models import Account as Acct
        applicant = db.session.get(Acct, app.applicant_id)
        entry = app.to_dict()
        entry['applicant'] = applicant.to_dict() if applicant else None
        result.append(entry)
    return paginated_response(result, total, page, per_page, 'Applicants loaded.')


@jobs_bp.route('/<job_id>/apply', methods=['POST'])
@lu_jwt_required
def apply_job(account, job_id):
    job = Job.query.get(job_id)
    if not job or not job.is_open:
        return error_response('Job not found or closed.', status_code=404)
    existing = Application.query.filter_by(job_id=job_id, applicant_id=account.id).first()
    if existing:
        return error_response('You have already applied for this job.')
    data = request.get_json(silent=True) or {}
    application = Application(
        id=str(uuid.uuid4()),
        job_id=job_id,
        applicant_id=account.id,
        cover_note=data.get('cover_note'),
        referred_by=data.get('referred_by'),
    )
    db.session.add(application)
    db.session.commit()
    return success_response('Application submitted.', application.to_dict(), status_code=201)


@jobs_bp.route('/<job_id>/save', methods=['POST'])
@lu_jwt_required
def save_job(account, job_id):
    job = Job.query.get(job_id)
    if not job:
        return error_response('Job not found.', status_code=404)
    saved = SavedJob.query.filter_by(job_id=job_id, account_id=account.id).first()
    if saved:
        db.session.delete(saved)
        db.session.commit()
        return success_response('Job unsaved.')
    saved = SavedJob(id=str(uuid.uuid4()), job_id=job_id, account_id=account.id)
    db.session.add(saved)
    db.session.commit()
    return success_response('Job saved.')
