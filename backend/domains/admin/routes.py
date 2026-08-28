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

def _dating_photo_url(entry):
    """dp.photos entries are normally {'url', 'caption'} dicts (see
    sparks/routes.py's photo endpoints) but tolerate a bare string too, in
    case an older client version ever wrote one directly."""
    return entry.get('url') if isinstance(entry, dict) else entry


def _dating_photo_entries(dp):
    """Turn a DatingProfile's `photos` JSON array into the same shape as
    UserPhoto.to_dict(), with a synthetic id ('dating:<index>') the delete
    endpoint recognizes — index-based, same convention sparks/routes.py's own
    DELETE /sparks/profile/photos/<photo_index> already uses, so this isn't
    a new scheme, just the existing one reused for the admin surface."""
    if not dp or not dp.photos:
        return []
    return [
        {
            'id': f'dating:{i}',
            'url': _dating_photo_url(entry),
            'is_profile_photo': i == 0,
            'is_cover_photo': False,
            'is_public': True,
            'caption': entry.get('caption') if isinstance(entry, dict) else None,
            'photo_type': 'dating',
            'sort_order': i,
            'created_at': None,
        }
        for i, entry in enumerate(dp.photos)
    ]


def _resolve_avatar(account_avatar, dp, fallback_photo_url=None):
    """Account.avatar is the professional/general avatar; a Sparks-only
    member typically never sets it — their real main photo is the first
    entry in DatingProfile.photos (see profile/routes.py's own comment on
    `dating_photos`: 'the dating wizard uploads here, not to account.avatar,
    so this is the real main photo source for a dating-only account'). The
    admin console must fall back to it the same way, or it just shows a
    blank avatar for someone who very much has a photo.

    `fallback_photo_url` is a last resort: the account's own best UserPhoto
    (see callers), for the case where real photos exist but none ever got
    flagged is_profile_photo (e.g. an admin uploaded several gallery photos
    without marking one primary) — PhotoService.upload now prevents this for
    new uploads, but this keeps already-affected accounts from showing a
    blank avatar despite genuinely having photos."""
    if account_avatar:
        return account_avatar
    if dp and dp.photos:
        return _dating_photo_url(dp.photos[0])
    return fallback_photo_url


@admin_v1_bp.route('/accounts', methods=['GET'])
@_admin_required
def list_accounts(account):
    """List all accounts with filters, enriched with a dating-profile summary
    (age, gender, bio, location, photo count) per row for the admin table —
    fetched in 3 bounded queries total (accounts page, dating profiles,
    photo counts), not per-row, regardless of page size."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    q = request.args.get('q', '').strip()
    status = request.args.get('status', '')
    kyc_level = request.args.get('kyc_level', None, type=int)
    gender = request.args.get('gender', '').strip()
    district_id = request.args.get('district_id', '').strip()

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
    if gender or district_id:
        from backend.domains.profile.models import DatingProfile as _DP
        dp_filter = db.session.query(_DP.account_id)
        if gender:
            dp_filter = dp_filter.filter(_DP.gender == gender)
        if district_id:
            dp_filter = dp_filter.filter(_DP.district_id == district_id)
        query = query.filter(Account.id.in_(dp_filter))

    query = query.order_by(Account.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)

    account_ids = [a.id for a in items]
    dating_by_account, photo_counts, district_names, fallback_avatar_by_account = {}, {}, {}, {}
    if account_ids:
        from datetime import date as _date
        from backend.domains.profile.models import DatingProfile
        from backend.domains.photos.models import UserPhoto
        from backend.domains.reference.models import Location

        dating_by_account = {
            dp.account_id: dp for dp in
            DatingProfile.query.filter(DatingProfile.account_id.in_(account_ids)).all()
        }
        photo_counts = dict(
            db.session.query(UserPhoto.account_id, func.count(UserPhoto.id))
            .filter(UserPhoto.account_id.in_(account_ids))
            .group_by(UserPhoto.account_id).all()
        )
        # Best-effort avatar fallback when no photo is flagged is_profile_photo
        # anywhere (see _resolve_avatar) — page-scoped, so bounded regardless
        # of page size.
        for p in (UserPhoto.query.filter(UserPhoto.account_id.in_(account_ids))
                  .order_by(UserPhoto.is_profile_photo.desc(), UserPhoto.sort_order.asc(),
                            UserPhoto.created_at.asc()).all()):
            fallback_avatar_by_account.setdefault(p.account_id, p.url)
        district_ids = {dp.district_id for dp in dating_by_account.values() if dp.district_id}
        if district_ids:
            district_names = {
                loc.id: loc.name for loc in
                Location.query.filter(Location.id.in_(district_ids)).all()
            }

    def _row(a):
        d = a.to_dict()
        dp = dating_by_account.get(a.id)
        # UserPhoto count + dating_profile.photos count — two genuinely
        # separate storage paths (see _resolve_avatar), both real photos.
        d['photo_count'] = photo_counts.get(a.id, 0) + (len(dp.photos) if dp and dp.photos else 0)
        d['avatar'] = _resolve_avatar(d['avatar'], dp, fallback_avatar_by_account.get(a.id))
        d['dating_profile_summary'] = None if not dp else {
            'age': (_date.today().year - dp.birth_year) if dp.birth_year else None,
            'gender': dp.gender,
            'bio': dp.bio,
            'relationship_goal': dp.relationship_goal,
            'location_label': district_names.get(dp.district_id),
        }
        return d

    return paginated_response(
        [_row(a) for a in items], total, page, per_page, 'Accounts loaded.'
    )


# 'inactive' is a soft, reversible dormancy marker (e.g. seed/demo accounts,
# or a member gone quiet) — distinct from 'suspended' (policy violation) and
# 'closed' (permanent, soft-deleted). Doesn't block login the way suspended
# does today, but naturally excludes the account from admin_login's
# `account_status != 'active'` check same as suspended already did.
_ACCOUNT_STATUSES = ('active', 'inactive', 'suspended', 'closed')

# Fields an admin may set on the nested profiles at creation time — a
# whitelist so the request body can't mass-assign arbitrary columns.
_DATING_PROFILE_FIELDS = {
    'bio', 'gender', 'looking_for_gender', 'sexual_orientation', 'birth_year',
    'relationship_goal', 'intent', 'height_cm', 'body_type', 'smoking',
    'drinking', 'marijuana', 'diet', 'exercise', 'education_level',
    'religion', 'religiosity', 'tribe_ethnicity', 'politics', 'industry',
    'languages_spoken', 'zodiac', 'personality_type', 'communication_style',
    'has_children', 'wants_children', 'country_code', 'district_id',
    'max_distance_km',
}
_PROFESSIONAL_PROFILE_FIELDS = {
    'headline', 'bio', 'seniority', 'current_role', 'industry',
    'years_experience', 'pronouns', 'tagline', 'availability_status',
}


def _generate_password(length=12):
    import secrets as _secrets
    import string as _string
    alphabet = _string.ascii_letters + _string.digits
    return ''.join(_secrets.choice(alphabet) for _ in range(length))


def _apply_whitelisted_fields(instance, data, allowed_fields):
    for field in allowed_fields:
        if field in data:
            setattr(instance, field, data[field])


@admin_v1_bp.route('/accounts', methods=['POST'])
@_admin_required
def create_account_admin(account):
    """
    Admin-created account with an optional complete profile in one request.

    Body: display_name (required), handle?, phone?, email?, password?,
    app_id? ('linkup'|'abanoonya', default 'linkup'), is_premium?,
    account_status? (active|inactive|suspended|closed, default active),
    modes?: {professional?, sparks?}, dating_profile?: {...}, professional_profile?: {...}

    At least one of phone/email is required — mirrors real signup, since an
    account needs a way to log in. If password is omitted, one is generated
    and returned ONCE in this response's `generated_password` — never
    logged, never retrievable afterward (matches the project's standing rule
    against ever using a fixed/shared default password).
    """
    data = request.get_json(silent=True) or {}
    display_name = (data.get('display_name') or '').strip()
    phone = (data.get('phone') or '').strip() or None
    email = (data.get('email') or '').strip().lower() or None
    handle = (data.get('handle') or '').strip().lower() or None

    if not display_name:
        return error_response('display_name is required.', status_code=400)
    if len(display_name) > 200:
        return error_response('display_name is too long (max 200 characters).', status_code=400)
    if not phone and not email:
        return error_response('At least one of phone or email is required.', status_code=400)

    if phone and Account.query.filter_by(phone=phone).first():
        return error_response('An account with that phone number already exists.', status_code=400)
    if email and Account.query.filter_by(email=email).first():
        return error_response('An account with that email already exists.', status_code=400)

    from backend.domains.identity.service import generate_handle
    if handle:
        if Account.query.filter_by(handle=handle).first():
            return error_response('That handle is already taken.', status_code=400)
    else:
        handle = generate_handle(display_name, phone or email)

    app_id = (data.get('app_id') or 'linkup').strip()
    if app_id not in ('linkup', 'abanoonya'):
        return error_response('app_id must be linkup or abanoonya.', status_code=400)

    account_status = (data.get('account_status') or 'active').strip()
    if account_status not in _ACCOUNT_STATUSES:
        return error_response(f'account_status must be one of: {", ".join(_ACCOUNT_STATUSES)}')

    modes_in = data.get('modes') or {}
    modes_enabled = {
        'professional': bool(modes_in.get('professional', app_id != 'abanoonya')),
        'sparks': bool(modes_in.get('sparks', app_id == 'abanoonya')),
    }

    password = (data.get('password') or '').strip()
    generated_password = None
    if not password:
        password = _generate_password()
        generated_password = password
    elif len(password) < 6:
        return error_response('Password must be at least 6 characters.', status_code=400)

    new_account = Account(
        handle=handle,
        display_name=display_name,
        phone=phone,
        email=email,
        phone_verified=1 if phone else 0,
        email_verified=1 if email else 0,
        app_id=app_id,
        modes_enabled=modes_enabled,
        account_status=account_status,
        is_premium=1 if data.get('is_premium') else 0,
        avatar=(data.get('avatar') or '').strip() or None,
    )
    new_account.set_password(password)
    db.session.add(new_account)
    db.session.flush()  # assigns new_account.id before the profile rows reference it

    dp_data = data.get('dating_profile')
    if modes_enabled['sparks'] and dp_data:
        from backend.domains.profile.models import DatingProfile
        from backend.domains.reference.models import Location
        dp = DatingProfile(account_id=new_account.id, display_name=display_name)
        _apply_whitelisted_fields(dp, dp_data, _DATING_PROFILE_FIELDS)
        # Derive region_id from the chosen district so the profile is
        # genuinely complete without asking the admin to pick both.
        if dp.district_id and not dp.region_id:
            district = db.session.get(Location, dp.district_id)
            if district and district.parent_id:
                dp.region_id = district.parent_id
        db.session.add(dp)

    pp_data = data.get('professional_profile')
    if modes_enabled['professional'] and pp_data:
        from backend.domains.profile.models import ProfessionalProfile
        pp = ProfessionalProfile(account_id=new_account.id)
        _apply_whitelisted_fields(pp, pp_data, _PROFESSIONAL_PROFILE_FIELDS)
        db.session.add(pp)

    db.session.commit()

    result = new_account.to_dict()
    if generated_password:
        result['generated_password'] = generated_password
    return success_response('Account created.', result, status_code=201)


@admin_v1_bp.route('/accounts/<account_id>', methods=['PUT'])
@_admin_required
def update_account_admin(account, account_id):
    """
    Full update of an existing account — the edit-mode counterpart of
    POST /v1/admin/accounts, sharing the same request shape and the same
    field whitelists, so the create/edit form on the frontend can be one
    component. Body: display_name?, handle?, phone?, email?, password?,
    app_id?, is_premium?, account_status? (active|inactive|suspended|closed),
    modes?: {professional?, sparks?},
    dating_profile?: {...}, professional_profile?: {...}.

    Turning a mode off does NOT delete that profile's row — just flips
    modes_enabled — so re-enabling it later doesn't lose data. Password is
    left untouched unless explicitly provided (unlike create, blank here
    does not generate a new one — an untouched field means "no change").
    """
    target = db.session.get(Account, account_id)
    # No deleted_at guard here (unlike the photo/premium endpoints below) —
    # a closed account must stay editable via account_status so it can be
    # reactivated; blocking every edit on deleted_at would make 'closed'
    # permanent even though it's meant to be a reversible status.
    if not target:
        return error_response('Account not found.', status_code=404)

    data = request.get_json(silent=True) or {}

    display_name = data.get('display_name')
    if display_name is not None:
        display_name = display_name.strip()
        if not display_name:
            return error_response('display_name cannot be empty.', status_code=400)
        if len(display_name) > 200:
            return error_response('display_name is too long (max 200 characters).', status_code=400)
        target.display_name = display_name

    if 'phone' in data:
        phone = (data.get('phone') or '').strip() or None
        if phone and Account.query.filter(Account.phone == phone, Account.id != account_id).first():
            return error_response('An account with that phone number already exists.', status_code=400)
        target.phone = phone

    if 'email' in data:
        email = (data.get('email') or '').strip().lower() or None
        if email and Account.query.filter(Account.email == email, Account.id != account_id).first():
            return error_response('An account with that email already exists.', status_code=400)
        target.email = email

    if not target.phone and not target.email:
        return error_response('At least one of phone or email is required.', status_code=400)

    if 'handle' in data:
        handle = (data.get('handle') or '').strip().lower()
        if handle and handle != target.handle:
            if Account.query.filter(Account.handle == handle, Account.id != account_id).first():
                return error_response('That handle is already taken.', status_code=400)
            target.handle = handle

    if 'app_id' in data:
        app_id = (data.get('app_id') or '').strip()
        if app_id not in ('linkup', 'abanoonya'):
            return error_response('app_id must be linkup or abanoonya.', status_code=400)
        target.app_id = app_id

    if 'is_premium' in data:
        target.is_premium = 1 if data['is_premium'] else 0

    if 'account_status' in data:
        new_status = (data.get('account_status') or '').strip()
        if new_status not in _ACCOUNT_STATUSES:
            return error_response(f'account_status must be one of: {", ".join(_ACCOUNT_STATUSES)}')
        if target.is_admin and new_status != 'active':
            return error_response('Cannot suspend another admin account.')
        target.account_status = new_status
        target.deleted_at = datetime.utcnow() if new_status == 'closed' else None

    password = (data.get('password') or '').strip()
    if password:
        if len(password) < 6:
            return error_response('Password must be at least 6 characters.', status_code=400)
        target.set_password(password)

    modes_in = data.get('modes')
    if modes_in is not None:
        current_modes = dict(target.modes)
        current_modes['professional'] = bool(modes_in.get('professional', current_modes.get('professional')))
        current_modes['sparks'] = bool(modes_in.get('sparks', current_modes.get('sparks')))
        target.modes_enabled = current_modes

    modes_now = target.modes

    dp_data = data.get('dating_profile')
    if modes_now.get('sparks') and dp_data is not None:
        from backend.domains.profile.models import DatingProfile
        from backend.domains.reference.models import Location
        dp = DatingProfile.query.filter_by(account_id=account_id).first()
        if not dp:
            dp = DatingProfile(account_id=account_id, display_name=target.display_name)
            db.session.add(dp)
        _apply_whitelisted_fields(dp, dp_data, _DATING_PROFILE_FIELDS)
        if dp.district_id and 'district_id' in dp_data:
            district = db.session.get(Location, dp.district_id)
            if district and district.parent_id:
                dp.region_id = district.parent_id

    pp_data = data.get('professional_profile')
    if modes_now.get('professional') and pp_data is not None:
        from backend.domains.profile.models import ProfessionalProfile
        pp = ProfessionalProfile.query.filter_by(account_id=account_id).first()
        if not pp:
            pp = ProfessionalProfile(account_id=account_id)
            db.session.add(pp)
        _apply_whitelisted_fields(pp, pp_data, _PROFESSIONAL_PROFILE_FIELDS)

    db.session.commit()
    return success_response('Account updated.', target.to_dict())


@admin_v1_bp.route('/accounts/<account_id>/photos', methods=['POST'])
@_admin_required
def upload_account_photo(account, account_id):
    """Upload one photo on behalf of a target account (multipart: field=photo,
    plus optional is_profile_photo/is_cover_photo/is_public/caption form
    fields) — reuses PhotoService.upload's exact logic (storage, avatar/cover
    sync, UserPhoto row) so admin-uploaded photos are indistinguishable from
    ones the member uploaded themselves. Scoped to admin-acting-on-behalf-of,
    unlike POST /v1/photos which uploads for the calling user."""
    target = db.session.get(Account, account_id)
    if not target or target.deleted_at:
        return error_response('Account not found.', status_code=404)

    from backend.domains.photos.service import PhotoService
    return PhotoService.upload(target, request)


@admin_v1_bp.route('/accounts/<account_id>/photos/<photo_id>', methods=['DELETE'])
@_admin_required
def delete_account_photo(account, account_id, photo_id):
    """Delete one of a target account's photos — reuses PhotoService.delete_photo,
    which also auto-promotes the next-most-recent photo to profile/cover if
    the deleted one held that role.

    A `dating:<index>` id (see _dating_photo_entries) refers to an entry in
    DatingProfile.photos rather than a UserPhoto row, so it's handled here
    directly instead of via PhotoService."""
    target = db.session.get(Account, account_id)
    if not target or target.deleted_at:
        return error_response('Account not found.', status_code=404)

    if photo_id.startswith('dating:'):
        from backend.domains.profile.models import DatingProfile
        dp = DatingProfile.query.filter_by(account_id=account_id).first()
        if not dp or not dp.photos:
            return error_response('Photo not found.', status_code=404)
        try:
            idx = int(photo_id.split(':', 1)[1])
        except ValueError:
            return error_response('Photo not found.', status_code=404)
        photos = list(dp.photos)
        if idx < 0 or idx >= len(photos):
            return error_response('Photo not found.', status_code=404)
        photos.pop(idx)
        dp.photos = photos
        db.session.commit()
        return success_response('Photo deleted.')

    from backend.domains.photos.service import PhotoService
    return PhotoService.delete_photo(target, photo_id)


@admin_v1_bp.route('/accounts/<account_id>', methods=['GET'])
@_admin_required
def get_account(account, account_id):
    """Get a single account detail, including the nested dating/professional
    profile and full photo list — the edit form (AccountFormModal) reads
    this to pre-populate itself."""
    target = db.session.get(Account, account_id)
    if not target:
        return error_response('Account not found.', status_code=404)
    data = target.to_dict()
    data['report_count'] = Report.query.filter_by(target_account_id=account_id).count()

    dating = None
    try:
        from backend.domains.profile.models import ProfessionalProfile, DatingProfile
        prof = ProfessionalProfile.query.filter_by(account_id=account_id).first()
        data['professional_profile'] = prof.to_dict() if prof else None
        dating = DatingProfile.query.filter_by(account_id=account_id).first()
        data['dating_profile'] = dating.to_dict() if dating else None
    except Exception:
        data['professional_profile'] = None
        data['dating_profile'] = None

    photos = []
    try:
        from backend.domains.photos.models import UserPhoto
        photos = UserPhoto.query.filter_by(account_id=account_id).order_by(
            UserPhoto.is_profile_photo.desc(), UserPhoto.sort_order.asc(),
            UserPhoto.created_at.desc(),
        ).all()
        # UserPhoto rows AND DatingProfile.photos are both real, separate
        # photo stores for this account (see _resolve_avatar) — surface
        # both here or a Sparks member's actual photos silently disappear
        # from the admin console despite genuinely existing.
        dating_entries = _dating_photo_entries(dating)
        data['photos'] = [p.to_dict() for p in photos] + dating_entries
        data['photo_count'] = len(data['photos'])
    except Exception:
        data['photo_count'] = 0
        data['photos'] = []

    data['avatar'] = _resolve_avatar(data['avatar'], dating, photos[0].url if photos else None)

    return success_response('Account loaded.', data)


def _apply_account_status(target, new_status, reason=''):
    """Shared by the single and bulk status endpoints: flips the status,
    fires the in-app + email notifications, commits nothing itself (caller
    controls the commit so bulk can do one commit for the whole batch)."""
    target.account_status = new_status
    target.deleted_at = datetime.utcnow() if new_status == 'closed' else None

    try:
        from backend.domains.notifications.service import create_notification
        msgs = {
            'suspended': ('Your account has been suspended',
                          reason or 'Your account has been suspended for violating our community guidelines.'),
            'active':    ('Your account has been reinstated', 'Your account is now active again. Welcome back!'),
            'inactive':  ('Your account is now inactive', reason or 'Your account has been marked inactive.'),
            'closed':    ('Your account has been closed', reason or 'Your account has been permanently closed.'),
        }
        title, body = msgs[new_status]
        create_notification(
            account_id=target.id,
            notif_type=f'admin.account_{new_status}',
            title=title, body=body,
            data={'reason': reason}, action_url='/support',
        )
    except Exception:
        pass

    if target.email:
        try:
            from backend.shared.email.service import send_account_status_email
            send_account_status_email(target.email, target.display_name, new_status, reason)
        except Exception:
            pass


@admin_v1_bp.route('/accounts/<account_id>/status', methods=['PUT'])
@_admin_required
def set_account_status(account, account_id):
    """
    Set account status: active | inactive | suspended | closed.
    Cannot suspend or modify another admin unless you are the same admin.
    """
    if account_id == account.id:
        return error_response('You cannot change your own account status.')

    target = db.session.get(Account, account_id)
    if not target:  # closed accounts stay reachable here so 'closed' is reversible
        return error_response('Account not found.', status_code=404)

    data = request.get_json(silent=True) or {}
    new_status = (data.get('status') or '').strip()
    reason = (data.get('reason') or '').strip()

    if new_status not in _ACCOUNT_STATUSES:
        return error_response(f'status must be one of: {", ".join(_ACCOUNT_STATUSES)}')

    if target.is_admin and new_status != 'active':
        return error_response('Cannot suspend another admin account.')

    _apply_account_status(target, new_status, reason)
    db.session.commit()
    return success_response(f'Account status set to {new_status}.', target.to_dict())


@admin_v1_bp.route('/accounts/bulk-status', methods=['PUT'])
@_admin_required
def bulk_set_account_status(account):
    """
    Apply one status to many accounts at once — the "select rows, then
    Activate/Deactivate" bulk action. Body: account_ids: [...], status
    (active|inactive|suspended|closed), reason?.

    Silently skips (doesn't fail the whole batch for) the caller's own
    account, other admin accounts (unless status is 'active'), and unknown
    ids — same protections as the single-account endpoint, just tallied
    instead of erroring, since a bulk action naturally spans a mixed
    selection an admin didn't hand-vet row by row.
    """
    data = request.get_json(silent=True) or {}
    account_ids = data.get('account_ids') or []
    new_status = (data.get('status') or '').strip()
    reason = (data.get('reason') or '').strip()

    if not isinstance(account_ids, list) or not account_ids:
        return error_response('account_ids must be a non-empty list.')
    if len(account_ids) > 500:
        return error_response('Select at most 500 accounts per batch.')
    if new_status not in _ACCOUNT_STATUSES:
        return error_response(f'status must be one of: {", ".join(_ACCOUNT_STATUSES)}')

    targets = Account.query.filter(Account.id.in_(account_ids)).all()
    found_ids = {t.id for t in targets}

    updated, skipped = 0, 0
    for target in targets:
        if target.id == account.id or (target.is_admin and new_status != 'active'):
            skipped += 1
            continue
        _apply_account_status(target, new_status, reason)
        updated += 1
    skipped += len(account_ids) - len(found_ids)  # ids that didn't resolve to a real account

    db.session.commit()
    return success_response(
        f'{updated} account(s) set to {new_status}' + (f', {skipped} skipped.' if skipped else '.'),
        {'updated': updated, 'skipped': skipped},
    )


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
