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
from backend.shared.storage.r2 import save_upload

profile_bp = Blueprint('v1_profile', __name__, url_prefix='/v1/profile')


def _coerce_date(v):
    """Lenient date parsing — accepts a year int/'YYYY', 'YYYY-MM', or full ISO
    date; returns a date or None. Lets the mobile send a year for experience."""
    if v in (None, ''):
        return None
    from datetime import date
    try:
        parts = str(v).strip().split('-')
        y = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 1
        d = int(parts[2]) if len(parts) > 2 else 1
        return date(y, max(1, min(12, m)), max(1, min(28, d)))
    except (ValueError, TypeError, IndexError):
        return None


def _get_full_profile(account_id: str, viewer_id: str = None) -> dict:
    """Build a full professional profile payload with completion score and stats."""
    from backend.domains.interest.models import InterestProfile, InterestTag
    from backend.domains.links.models import Link
    from sqlalchemy import or_

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

    # Completion score. The dating section is included only for the owner's own
    # view so a stranger never learns the member runs the Sparks lens (mode sep).
    from backend.domains.interest.models import InterestProfile as _IP
    _ic = _IP.query.filter_by(account_id=account_id).count()
    _dating = None
    if viewer_id == account_id:
        _dating = DatingProfile.query.filter_by(account_id=account_id).first()
    completion = calculate_completion(account, prof, edu, exp, _ic, dating_profile=_dating)

    # Build profile dict with completion + resolved location
    prof_dict = prof.to_dict() if prof else {}
    if prof_dict:
        prof_dict['completion_score'] = completion['score']
        if prof and prof.location_id:
            from backend.domains.reference.models import Location
            loc = db.session.get(Location, prof.location_id)
            if loc:
                prof_dict['location'] = loc.to_dict()

    # ── Real stats ──────────────────────────────────────────────────────────────
    connection_count = Link.query.filter(
        or_(Link.requester_id == account_id, Link.addressee_id == account_id),
        Link.status == 'accepted',
    ).count()

    hub_posts_count = 0
    try:
        from backend.domains.hubs.models import HubPost
        hub_posts_count = HubPost.query.filter_by(account_id=account_id).filter(
            HubPost.deleted_at.is_(None)
        ).count()
    except Exception:
        pass

    stats = {
        'profile_views': prof.profile_views if prof else 0,
        'connections':   connection_count,
        'hubs':          hub_posts_count,
    }

    return {
        'account':              account.to_dict(),
        'profile':              prof_dict,
        'professional_profile': prof_dict,
        'education':            [e.to_dict() for e in edu],
        'experience':           [e.to_dict() for e in exp],
        'certifications':       [c.to_dict() for c in certs],
        'interests':            interests,
        'completion':           completion,
        'stats':                stats,
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
                  'visibility_mode', 'open_to', 'location_id',
                  # 360° depth (T-API-100)
                  'pronouns', 'tagline', 'industry', 'years_experience',
                  'availability_status', 'social_links', 'portfolio_urls',
                  'achievements', 'languages_spoken', 'location_origin_id',
                  'hourly_rate', 'hourly_rate_currency', 'profile_video_url']:
        if field in data:
            setattr(prof, field, data[field])

    # Light validation on enum-ish / numeric fields
    if prof.availability_status not in (None, 'open', 'casually_looking', 'not_looking'):
        return error_response("availability_status must be one of: open, casually_looking, not_looking.")
    if prof.years_experience is not None:
        try:
            prof.years_experience = max(0, int(prof.years_experience))
        except (ValueError, TypeError):
            return error_response("years_experience must be a number.")

    db.session.commit()
    return success_response('Profile updated.', _get_full_profile(account.id))


@profile_bp.route('/me/photo', methods=['POST'])
@lu_jwt_required
def upload_photo(account):
    file = (request.files.get('photo') or request.files.get('avatar')
            or request.files.get('cover'))
    if not file:
        return error_response('No photo file provided.')
    # type=cover updates the cover banner; otherwise the profile avatar.
    kind = (request.form.get('type') or 'avatar').lower()
    is_cover = kind == 'cover'
    url = save_upload(file, folder='covers' if is_cover else 'avatars')
    if not url:
        return error_response('Failed to upload photo. Please use JPG, PNG, or WebP.')
    if is_cover:
        account.cover_photo = url
        db.session.commit()
        return success_response('Cover uploaded.', {'cover_photo': url})
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
    # Increment profile views (non-self views only)
    if prof and target.id != account.id:
        prof.profile_views = (prof.profile_views or 0) + 1
        db.session.commit()
        from backend.shared.events.emit import emit
        emit('profile.view', account_id=account.id, object_type='account', object_id=target.id)
    payload = _get_full_profile(target.id, viewer_id=account.id)
    return success_response('Profile loaded.', payload)


@profile_bp.route('/me/dating', methods=['GET'])
@lu_jwt_required
def get_dating_profile(account):
    prof = DatingProfile.query.filter_by(account_id=account.id).first()
    return success_response('Dating profile loaded.', prof.to_dict() if prof else None)


@profile_bp.route('/me/dating', methods=['DELETE'])
@lu_jwt_required
def delete_dating_profile(account):
    """Remove dating profile — sets discoverability to paused (soft) or deletes record."""
    prof = DatingProfile.query.filter_by(account_id=account.id).first()
    if not prof:
        return error_response('No dating profile found.', status_code=404)
    # Soft approach: set discoverability=paused so they can restore later
    # Hard delete available via ?permanent=true
    permanent = request.args.get('permanent', '').lower() == 'true'
    if permanent:
        db.session.delete(prof)
        # Also disable sparks mode
        modes = dict(account.modes)  # safe accessor (T-API-041)
        modes['sparks'] = False
        account.modes_enabled = modes
        db.session.commit()
        return success_response('Dating profile deleted permanently.')
    # Soft: pause discoverability
    prof.discoverability = 'paused'
    db.session.commit()
    return success_response('Dating profile paused. You are no longer visible in Sparks.',
                            prof.to_dict())


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

    valid_disc = {'discoverable', 'paused', 'incognito'}
    for field in ['display_name', 'bio', 'age_min', 'age_max', 'birth_year',
                  'gender', 'looking_for_gender', 'intent', 'lifestyle', 'prompts',
                  # 360° depth (T-API-101)
                  'height_cm', 'relationship_goal', 'has_children', 'wants_children',
                  'smoking', 'drinking', 'religion', 'religiosity', 'tribe_ethnicity',
                  'education_level', 'love_languages', 'personality_type', 'diet',
                  'exercise', 'pets', 'voice_prompt_url', 'deal_breakers',
                  'sensitive_optin', 'photos', 'max_distance_km',
                  # Deeper attributes (P-API-03)
                  'sexual_orientation', 'marijuana', 'politics', 'body_type',
                  'zodiac', 'communication_style', 'languages_spoken', 'industry',
                  'region_id', 'district_id', 'country_code', 'preferences']:
        if field in data:
            val = data[field]
            if field == 'intent' and isinstance(val, str):
                val = intent_map.get(val.lower(), val)
            setattr(prof, field, val)
    if 'discoverability' in data:
        disc = data['discoverability']
        if disc not in valid_disc:
            return error_response(f'discoverability must be one of: {", ".join(valid_disc)}')
        if disc == 'incognito' and not account.is_premium:
            return error_response(
                'Incognito mode requires LinkUp+ premium. Upgrade to hide your profile while browsing.',
                status_code=403
            )
        prof.discoverability = disc

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
    # Accept 'institution' as an alias for 'institution_name' (mobile compat)
    institution_name = data.get('institution_name') or data.get('institution')
    edu = Education(
        id=str(uuid.uuid4()),
        account_id=account.id,
        institution_id=data.get('institution_id'),
        institution_name=institution_name,
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
    # Accept 'company' as an alias for 'org_name' (mobile compat)
    org_name = data.get('org_name') or data.get('company')
    exp = Experience(
        id=str(uuid.uuid4()),
        account_id=account.id,
        org_id=data.get('org_id'),
        org_name=org_name,
        title=data['title'],
        description=data.get('description'),
        start_date=_coerce_date(data.get('start_date')),
        end_date=_coerce_date(data.get('end_date')),
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
    for field in ['org_id', 'org_name', 'title', 'description', 'is_current']:
        if field in data:
            setattr(exp, field, data[field])
    if 'start_date' in data:
        exp.start_date = _coerce_date(data['start_date'])
    if 'end_date' in data:
        exp.end_date = _coerce_date(data['end_date'])
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


# ─── Member's public posts ───────────────────────────────────

@profile_bp.route('/@<handle>/posts', methods=['GET'])
@lu_jwt_required
def member_posts(account, handle):
    """List a member's public hub posts (most recent first)."""
    from backend.domains.hubs.models import HubPost
    normalized = handle.lower().replace('-', '_')
    target = Account.query.filter(
        Account.handle.ilike(normalized),
        Account.deleted_at.is_(None),
    ).first()
    if not target:
        return error_response('Profile not found.', status_code=404)

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    from backend.shared.utils.pagination import paginate_query
    from backend.shared.utils.response import paginated_response
    query = HubPost.query.filter_by(account_id=target.id).filter(
        HubPost.deleted_at.is_(None)
    ).order_by(HubPost.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)

    result = []
    for post in items:
        from backend.domains.hubs.models import Hub
        hub = db.session.get(Hub, post.hub_id)
        pd = post.to_dict()
        pd['hub'] = {'id': hub.id, 'name': hub.name, 'slug': hub.slug} if hub else None
        result.append(pd)

    return paginated_response(result, total, page, per_page, 'Posts loaded.')


# ─── Compatibility ───────────────────────────────────────────

@profile_bp.route('/compatibility/<target_id>', methods=['GET'])
@lu_jwt_required
def compatibility(account, target_id):
    """Return Interest Graph compatibility breakdown with another account."""
    from backend.shared.scoring.interest_graph import get_compatibility_breakdown
    mode = request.args.get('mode', 'professional')
    target = db.session.get(Account, target_id)
    if not target or target.deleted_at:
        return error_response('Account not found.', status_code=404)
    breakdown = get_compatibility_breakdown(account.id, target_id, mode=mode)
    return success_response('Compatibility loaded.', breakdown)


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


@profile_bp.route('/me/certifications/<cert_id>', methods=['PUT'])
@lu_jwt_required
def update_certification(account, cert_id):
    """Update an existing certification."""
    cert = Certification.query.filter_by(id=cert_id, account_id=account.id).first()
    if not cert:
        return error_response('Certification not found.', status_code=404)
    data = request.get_json(silent=True) or {}
    for field in ['name', 'issuer', 'issued_at', 'expires_at', 'credential_url']:
        if field in data:
            setattr(cert, field, data[field])
    db.session.commit()
    return success_response('Certification updated.', cert.to_dict())


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

@profile_bp.route('/<account_id>', methods=['GET'])
@lu_jwt_required
def get_profile_by_id(account, account_id):
    """
    GET /v1/profile/<account_id>
    Public profile view by UUID.  Respects visibility_mode.
    Increments profile_views (non-self only).
    """
    if account_id == 'me':
        payload = _get_full_profile(account.id, viewer_id=account.id)
        return success_response('Profile loaded.', payload)

    target = db.session.get(Account, account_id)
    if not target or target.deleted_at:
        return error_response('Profile not found.', status_code=404)

    prof = ProfessionalProfile.query.filter_by(account_id=target.id).first()
    if prof and prof.visibility_mode == 'self_only' and target.id != account.id:
        return error_response('This profile is private.', status_code=403)

    if target.id != account.id and prof:
        prof.profile_views = (prof.profile_views or 0) + 1
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    payload = _get_full_profile(target.id, viewer_id=account.id)
    return success_response('Profile loaded.', payload)


@profile_bp.route('/completion', methods=['GET'])
@lu_jwt_required
def completion(account):
    """
    GET /v1/profile/me/completion
    Returns the profile completion score, per-check booleans, and the ordered
    list of onboarding steps (done/pending) so the mobile app can build the
    setup UI without any extra logic.
    """
    from backend.domains.interest.models import InterestProfile
    prof = ProfessionalProfile.query.filter_by(account_id=account.id).first()
    edu  = Education.query.filter_by(account_id=account.id).all()
    exp  = Experience.query.filter_by(account_id=account.id).all()
    interests_count = InterestProfile.query.filter_by(account_id=account.id).count()
    dating = DatingProfile.query.filter_by(account_id=account.id).first()
    result = calculate_completion(account, prof, edu, exp, interests_count, dating_profile=dating)
    return success_response('Profile completion loaded.', result)


@profile_bp.route('/journey', methods=['GET'])
@lu_jwt_required
def journey(account):
    """Journey state + next-best-actions (T-API-081).

    Tells the app what the member should do next: a ranked, mode-aware list of
    actions derived from profile completeness and pending social signals.
    """
    from backend.domains.interest.models import InterestProfile
    from backend.domains.links.models import Link
    prof = ProfessionalProfile.query.filter_by(account_id=account.id).first()
    edu = Education.query.filter_by(account_id=account.id).all()
    exp = Experience.query.filter_by(account_id=account.id).all()
    interests_count = InterestProfile.query.filter_by(account_id=account.id).count()
    dating = DatingProfile.query.filter_by(account_id=account.id).first()
    comp = calculate_completion(account, prof, edu, exp, interests_count, dating_profile=dating)

    score = comp['score']
    stage = ('new' if score < 25 else 'building' if score < 60
             else 'active' if score < 85 else 'complete')

    actions = []

    # Completeness-driven actions, ranked by the impact of finishing each section.
    _SECTION_ACTIONS = {
        'basics':            ('Complete your basics', 'Add a photo, headline and bio', '/profile/edit'),
        'professional':      ('Round out your work profile', 'Add your role, seniority and industry', '/profile/edit'),
        'professional_depth':('Stand out professionally', 'Add social links, languages and achievements', '/profile/edit'),
        'education':         ('Add your education', 'Alumni connections start here', '/profile/education'),
        'experience':        ('Add your experience', 'Show your career journey', '/profile/experience'),
        'interests':         ('Pick at least 5 interests', 'Powers every recommendation', '/onboarding/interests'),
        'dating':            ('Polish your Sparks profile', 'Add photos and prompts to appear in more decks', '/sparks/profile'),
    }
    for key, sec in sorted(comp.get('sections', {}).items(), key=lambda kv: kv[1]['pct']):
        if not sec['complete'] and key in _SECTION_ACTIONS:
            title, body, url = _SECTION_ACTIONS[key]
            actions.append({
                'type': f'complete.{key}',
                'title': title, 'body': body, 'cta': 'Complete', 'action_url': url,
                'impact_pct': round((sec['total'] - sec['filled']) / max(sec['total'], 1) * 100),
                'priority': 100 - sec['pct'],
            })

    # Signal-driven actions.
    pending = Link.query.filter_by(addressee_id=account.id, status='requested').count()
    if pending:
        actions.append({
            'type': 'links.pending', 'title': f'{pending} pending Link request{"s" if pending > 1 else ""}',
            'body': 'Review who wants to connect with you.', 'cta': 'Review',
            'action_url': '/links/requests', 'impact_pct': 0, 'priority': 90,
        })

    actions.sort(key=lambda a: -a['priority'])

    return success_response('Journey loaded.', {
        'onboarding_stage': stage,
        'profile_completion': score,
        'sections_overall': comp.get('sections_overall'),
        'next_best_actions': actions[:5],
    })


@profile_bp.route('/me/stats', methods=['GET'])
@lu_jwt_required
def my_profile_stats(account):
    """
    Profile statistics for the current account.
    Returns profile views, connections, endorsements, and job stats.
    """
    from backend.domains.links.models import Link
    from backend.domains.endorsements.routes import Endorsement
    from backend.domains.jobs.models import Application
    from sqlalchemy import or_

    prof = ProfessionalProfile.query.filter_by(account_id=account.id).first()
    connection_count = Link.query.filter(
        or_(Link.requester_id == account.id, Link.addressee_id == account.id),
        Link.status == 'accepted',
    ).count()
    endorsements_received = Endorsement.query.filter_by(endorsee_id=account.id).count()
    applications_sent = Application.query.filter_by(applicant_id=account.id).count()
    hub_posts_count = 0
    try:
        from backend.domains.hubs.models import HubPost
        hub_posts_count = HubPost.query.filter_by(
            account_id=account.id
        ).filter(HubPost.deleted_at.is_(None)).count()
    except Exception:
        pass

    return success_response('Profile stats loaded.', {
        'profile_views': prof.profile_views if prof else 0,
        'connections': connection_count,
        'endorsements_received': endorsements_received,
        'applications_sent': applications_sent,
        'hub_posts': hub_posts_count,
    })
