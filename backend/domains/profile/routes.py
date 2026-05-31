"""
Profile routes: /v1/profile/*
"""
import uuid
from flask import Blueprint, request
from backend.models import db
from backend.domains.identity.models import Account
from backend.domains.profile.models import ProfessionalProfile, DatingProfile, Education, Experience, Certification
from backend.domains.profile.service import calculate_completion
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.utils.response import success_response, error_response
from backend.shared.storage.local import save_upload

profile_bp = Blueprint('v1_profile', __name__, url_prefix='/v1/profile')


def _get_full_profile(account_id: str, viewer_id: str = None) -> dict:
    """Build a full professional profile payload with completion score."""
    from backend.domains.interest.models import InterestProfile, InterestTag
    account = db.session.get(Account, account_id)
    if not account:
        return None
    prof = ProfessionalProfile.query.filter_by(account_id=account_id).first()
    edu = Education.query.filter_by(account_id=account_id).order_by(Education.start_year.desc()).all()
    exp = Experience.query.filter_by(account_id=account_id).order_by(Experience.start_date.desc()).all()
    certs = Certification.query.filter_by(account_id=account_id).all()

    # Interests (professional mode only for public view)
    interests_q = InterestProfile.query.filter_by(account_id=account_id)
    if viewer_id != account_id:
        interests_q = interests_q.filter(InterestProfile.mode.in_(['professional', 'both']))
    interest_profiles = interests_q.all()
    interests = []
    for ip in interest_profiles:
        tag = db.session.get(InterestTag, ip.tag_id)
        if tag:
            interests.append({**tag.to_dict(), 'weight': float(ip.weight or 0), 'pinned': bool(ip.pinned)})

    # Completion score
    completion = calculate_completion(account, prof, edu, exp)

    # Build profile dict with completion embedded
    prof_dict = prof.to_dict() if prof else {}
    if prof_dict:
        prof_dict['completion_score'] = completion['score']

    return {
        'account': account.to_dict(),
        'profile': prof_dict,                          # alias for front-end convenience
        'professional_profile': prof_dict,             # keep for backward compat
        'education': [e.to_dict() for e in edu],
        'experience': [e.to_dict() for e in exp],
        'certifications': [c.to_dict() for c in certs],
        'interests': interests,
        'completion': completion,
    }


@profile_bp.route('/me', methods=['GET'])
@lu_jwt_required
def get_my_profile(account):
    payload = _get_full_profile(account.id, viewer_id=account.id)
    return success_response('Profile loaded.', payload)


@profile_bp.route('/me', methods=['PUT'])
@lu_jwt_required
def update_my_profile(account):
    data = request.get_json(silent=True) or {}

    # Update account fields
    for field in ['display_name', 'email']:
        if field in data:
            setattr(account, field, data[field])

    # Get or create professional profile
    prof = ProfessionalProfile.query.filter_by(account_id=account.id).first()
    if not prof:
        prof = ProfessionalProfile(id=str(uuid.uuid4()), account_id=account.id)
        db.session.add(prof)

    for field in ['headline', 'bio', 'seniority', 'current_role', 'current_org_id',
                  'visibility_mode', 'open_to', 'location_id']:
        if field in data:
            setattr(prof, field, data[field])

    db.session.commit()
    return success_response('Profile updated.', _get_full_profile(account.id))


@profile_bp.route('/me/photo', methods=['POST'])
@lu_jwt_required
def upload_photo(account):
    file = request.files.get('photo') or request.files.get('avatar')
    if not file:
        return error_response('No photo file provided.')
    url = save_upload(file, folder='avatars')
    if not url:
        return error_response('Failed to upload photo. Please use JPG, PNG, or WebP.')
    account.avatar = url
    db.session.commit()
    return success_response('Photo uploaded.', {'avatar': url})


@profile_bp.route('/@<handle>', methods=['GET'])
@lu_jwt_required
def get_profile_by_handle(account, handle):
    # Normalize: hyphens → underscores, lowercase (for URL-friendly aliases)
    normalized = handle.lower().replace('-', '_')
    target = Account.query.filter(
        Account.handle.ilike(normalized),
        Account.deleted_at.is_(None)
    ).first()
    if not target:
        return error_response('Profile not found.', status_code=404)
    prof = ProfessionalProfile.query.filter_by(account_id=target.id).first()
    if prof and prof.visibility_mode == 'self_only' and target.id != account.id:
        return error_response('This profile is private.', status_code=403)
    payload = _get_full_profile(target.id, viewer_id=account.id)
    return success_response('Profile loaded.', payload)


@profile_bp.route('/me/dating', methods=['GET'])
@lu_jwt_required
def get_dating_profile(account):
    prof = DatingProfile.query.filter_by(account_id=account.id).first()
    return success_response('Dating profile loaded.', prof.to_dict() if prof else None)


@profile_bp.route('/me/dating', methods=['PUT'])
@lu_jwt_required
def update_dating_profile(account):
    data = request.get_json(silent=True) or {}
    prof = DatingProfile.query.filter_by(account_id=account.id).first()
    if not prof:
        prof = DatingProfile(id=str(uuid.uuid4()), account_id=account.id)
        db.session.add(prof)

    # Intent enum normalization: map long-form values to DB enum values
    intent_map = {
        'serious_relationship': 'serious', 'serious relationship': 'serious',
        'casual_dating': 'casual', 'casual dating': 'casual',
        'friendship_first': 'friendship', 'friendship': 'friendship',
        'marriage_minded': 'serious',
        'open': 'open',
    }

    for field in ['display_name', 'bio', 'age_min', 'age_max', 'intent', 'lifestyle', 'prompts']:
        if field in data:
            val = data[field]
            if field == 'intent' and isinstance(val, str):
                val = intent_map.get(val.lower(), val)
            setattr(prof, field, val)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return error_response(f'Could not update dating profile: {str(e)}', status_code=422)

    return success_response('Dating profile updated.', prof.to_dict())


# ─── Education ───────────────────────────────────────────────

@profile_bp.route('/me/education', methods=['POST'])
@lu_jwt_required
def add_education(account):
    data = request.get_json(silent=True) or {}
    edu = Education(
        id=str(uuid.uuid4()),
        account_id=account.id,
        institution_id=data.get('institution_id'),
        institution_name=data.get('institution_name'),
        degree=data.get('degree'),
        field=data.get('field'),
        start_year=data.get('start_year'),
        end_year=data.get('end_year'),
    )
    db.session.add(edu)
    db.session.commit()
    return success_response('Education added.', edu.to_dict(), status_code=201)


@profile_bp.route('/me/education/<edu_id>', methods=['PUT'])
@lu_jwt_required
def update_education(account, edu_id):
    edu = Education.query.filter_by(id=edu_id, account_id=account.id).first()
    if not edu:
        return error_response('Education record not found.', status_code=404)
    data = request.get_json(silent=True) or {}
    for field in ['institution_id', 'institution_name', 'degree', 'field', 'start_year', 'end_year']:
        if field in data:
            setattr(edu, field, data[field])
    db.session.commit()
    return success_response('Education updated.', edu.to_dict())


@profile_bp.route('/me/education/<edu_id>', methods=['DELETE'])
@lu_jwt_required
def delete_education(account, edu_id):
    edu = Education.query.filter_by(id=edu_id, account_id=account.id).first()
    if not edu:
        return error_response('Education record not found.', status_code=404)
    db.session.delete(edu)
    db.session.commit()
    return success_response('Education removed.')


# ─── Experience ──────────────────────────────────────────────

@profile_bp.route('/me/experience', methods=['POST'])
@lu_jwt_required
def add_experience(account):
    data = request.get_json(silent=True) or {}
    if not data.get('title'):
        return error_response('Job title is required.')
    exp = Experience(
        id=str(uuid.uuid4()),
        account_id=account.id,
        org_id=data.get('org_id'),
        org_name=data.get('org_name'),
        title=data['title'],
        description=data.get('description'),
        start_date=data.get('start_date'),
        end_date=data.get('end_date'),
        is_current=int(data.get('is_current', 0)),
    )
    db.session.add(exp)
    db.session.commit()
    return success_response('Experience added.', exp.to_dict(), status_code=201)


@profile_bp.route('/me/experience/<exp_id>', methods=['PUT'])
@lu_jwt_required
def update_experience(account, exp_id):
    exp = Experience.query.filter_by(id=exp_id, account_id=account.id).first()
    if not exp:
        return error_response('Experience record not found.', status_code=404)
    data = request.get_json(silent=True) or {}
    for field in ['org_id', 'org_name', 'title', 'description', 'start_date', 'end_date', 'is_current']:
        if field in data:
            setattr(exp, field, data[field])
    db.session.commit()
    return success_response('Experience updated.', exp.to_dict())


@profile_bp.route('/me/experience/<exp_id>', methods=['DELETE'])
@lu_jwt_required
def delete_experience(account, exp_id):
    exp = Experience.query.filter_by(id=exp_id, account_id=account.id).first()
    if not exp:
        return error_response('Experience record not found.', status_code=404)
    db.session.delete(exp)
    db.session.commit()
    return success_response('Experience removed.')


# ─── Account deletion ────────────────────────────────────────

@profile_bp.route('/me', methods=['DELETE'])
@lu_jwt_required
def delete_account(account):
    from datetime import datetime
    account.deleted_at = datetime.utcnow()
    account.account_status = 'closed'
    db.session.commit()
    return success_response('Account deleted.')


# ─── Certifications ──────────────────────────────────────────

@profile_bp.route('/me/certifications', methods=['POST'])
@lu_jwt_required
def add_certification(account):
    data = request.get_json(silent=True) or {}
    if not data.get('name'):
        return error_response('Certification name is required.')
    cert = Certification(
        id=str(uuid.uuid4()),
        account_id=account.id,
        name=data['name'],
        issuer=data.get('issuer'),
        issued_at=data.get('issued_at'),
        expires_at=data.get('expires_at'),
        credential_url=data.get('credential_url'),
    )
    db.session.add(cert)
    db.session.commit()
    return success_response('Certification added.', cert.to_dict(), status_code=201)


@profile_bp.route('/me/certifications/<cert_id>', methods=['DELETE'])
@lu_jwt_required
def delete_certification(account, cert_id):
    cert = Certification.query.filter_by(id=cert_id, account_id=account.id).first()
    if not cert:
        return error_response('Certification not found.', status_code=404)
    db.session.delete(cert)
    db.session.commit()
    return success_response('Certification removed.')


# ─── Completion ──────────────────────────────────────────────

@profile_bp.route('/completion', methods=['GET'])
@lu_jwt_required
def completion(account):
    prof = ProfessionalProfile.query.filter_by(account_id=account.id).first()
    edu = Education.query.filter_by(account_id=account.id).all()
    exp = Experience.query.filter_by(account_id=account.id).all()
    score = calculate_completion(account, prof, edu, exp)
    return success_response('Profile completion loaded.', score)
