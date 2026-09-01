"""
Admin v1 routes: /v1/admin/*
All endpoints require is_admin=1 on the calling account.
"""
import re
from datetime import datetime, timedelta
from flask import Blueprint, request
from sqlalchemy import func, or_
from backend.models import db
from backend.domains.identity.models import Account
from backend.domains.safety.models import Report
from backend.domains.subscriptions.models import SubscriptionPlan, Subscription
from backend.shared.app_brand import DATING_ONLY_APP_IDS, VALID_APP_IDS
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.ratelimit import rate_limit
from backend.shared.utils.response import success_response, error_response, paginated_response
from backend.shared.utils.pagination import paginate_query

admin_v1_bp = Blueprint('v1_admin', __name__, url_prefix='/v1/admin')


@admin_v1_bp.route('/login', methods=['POST'])
@rate_limit(10, 60, body_field='identifier')
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

    # Collapsed into one generic response: previously "no account", "not an
    # admin", and "wrong password" each returned a distinct message, which
    # let anyone probe an identifier and learn whether it exists and whether
    # it's an admin account — turning this endpoint into a free admin-account
    # enumeration oracle. Only a genuinely correct admin password unlocks any
    # further detail (e.g. the suspended check below).
    if not account or not account.is_admin or not account.check_password(password):
        return error_response('Invalid credentials.', status_code=401)

    if account.account_status != 'active':
        return error_response('This account is suspended or closed.', status_code=403)

    tokens = issue_tokens(account)
    return success_response('Login successful.', {**account.to_dict(include_private=True), **tokens})


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


# ─── Engagement Analytics ───────────────────────────────────────────────────────
# Aggregation layer over the same BehavioralEvent stream /events above exposes
# raw — DAU/WAU/MAU, trending profiles (with real scores, unlike the coarse
# sampled version members see at GET /v1/sparks/trending), a contact-reveal
# audit trail, and per-account engagement for AccountDetailDrawer.

@admin_v1_bp.route('/analytics/overview', methods=['GET'])
@_admin_required
def analytics_overview(account):
    """?app_id= (required — DAU/WAU/MAU and event volume are meaningless
    mixed across the two brands)."""
    from backend.domains.analytics.service import get_engagement_overview
    app_id = (request.args.get('app_id') or 'abanoonya').strip()
    return success_response('Engagement overview loaded.', get_engagement_overview(app_id))


@admin_v1_bp.route('/analytics/trending', methods=['GET'])
@_admin_required
def analytics_trending(account):
    """Real trending scores — never exposed to members (see
    GET /v1/sparks/trending, which only ever returns a randomized sample
    with no score attached)."""
    from backend.domains.analytics.service import get_trending_account_ids
    app_id = (request.args.get('app_id') or 'abanoonya').strip()
    limit = min(request.args.get('limit', 30, type=int), 100)
    ranked = get_trending_account_ids(app_id, limit=limit)
    ids = [aid for aid, _ in ranked]
    accounts = {a.id: a for a in Account.query.filter(Account.id.in_(ids)).all()} if ids else {}
    # account_status/discoverability included deliberately: this score comes
    # from historical events and doesn't itself check either — an account
    # paused or deactivated after the events that earned it a high score can
    # still show up here. Surfacing status inline stops that from silently
    # reading as "currently live and trending" to whoever's looking at this list.
    items = [
        {
            'account_id': aid, 'score': score,
            'display_name': accounts[aid].display_name if aid in accounts else None,
            'avatar': accounts[aid].avatar if aid in accounts else None,
            'account_status': accounts[aid].account_status if aid in accounts else None,
        }
        for aid, score in ranked
    ]
    return success_response('Trending profiles loaded.', items)


@admin_v1_bp.route('/analytics/contacts', methods=['GET'])
@_admin_required
def analytics_contacts(account):
    """Contact-reveal audit log: who revealed whose number/WhatsApp, when."""
    from backend.domains.analytics.service import get_contact_reveal_audit
    app_id = (request.args.get('app_id') or 'abanoonya').strip()
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    rows, total, p, last_page, pp = get_contact_reveal_audit(app_id, page, per_page)
    return paginated_response(rows, total, p, pp, 'Contact reveals loaded.')


@admin_v1_bp.route('/analytics/account/<account_id>', methods=['GET'])
@_admin_required
def analytics_account(account, account_id):
    """Per-account engagement snapshot — presence, location freshness, and
    30-day action counts given/received. Feeds AccountDetailDrawer's
    Engagement section, sitting next to the account's existing status/
    premium controls so a spike in activity is actionable, not just visible."""
    from backend.domains.analytics.service import get_account_engagement
    data = get_account_engagement(account_id)
    if not data:
        return error_response('Account not found.', status_code=404)
    return success_response('Account engagement loaded.', data)


@admin_v1_bp.route('/stats', methods=['GET'])
@_admin_required
def stats(account):
    """Platform-wide stats snapshot. ?app_id=linkup|abanoonya scopes the account
    counts to one brand; omit for both combined (accounts are the only rows that
    carry app_id — content/moderation stay platform-wide since they reference
    accounts from either app interchangeably, e.g. a LinkUp user's hub post)."""
    from backend.domains.hubs.models import Hub, HubPost
    from backend.domains.jobs.models import Job
    from backend.domains.events.models import Event
    from backend.domains.sparks.models import Match
    from backend.domains.links.models import Link
    from backend.domains.notifications.models import Notification

    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    app_id = request.args.get('app_id', '').strip()

    def _acct(q):
        return q.filter(Account.app_id == app_id) if app_id else q

    data = {
        'accounts': {
            'total': _acct(Account.query.filter(Account.deleted_at.is_(None))).count(),
            'active': _acct(Account.query.filter(
                Account.account_status == 'active',
                Account.deleted_at.is_(None)
            )).count(),
            'premium': _acct(Account.query.filter(Account.is_premium == 1)).count(),
            'new_today': _acct(Account.query.filter(Account.created_at >= day_ago)).count(),
            'new_this_week': _acct(Account.query.filter(Account.created_at >= week_ago)).count(),
            'suspended': _acct(Account.query.filter(Account.account_status == 'suspended')).count(),
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
            'open_panic_alerts': _open_panic_count(),
            'pending_kyc': _pending_kyc_count(),
            'pending_institutions': _pending_institution_count(),
            'pending_withdrawals': _pending_withdrawal_count(),
        },
    }
    return success_response('Stats loaded.', data)


def _open_panic_count():
    try:
        from backend.domains.safety.models import PanicAlert
        return PanicAlert.query.filter_by(status='open').count()
    except Exception:
        return 0


def _pending_kyc_count():
    try:
        from backend.domains.identity.models import Verification
        return Verification.query.filter_by(status='pending').count()
    except Exception:
        return 0


def _pending_institution_count():
    from backend.domains.reference.models import Institution
    return Institution.query.filter_by(verified=0).count()


def _pending_withdrawal_count():
    from backend.domains.wallet.models import Withdrawal
    return Withdrawal.query.filter_by(status='review').count()


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
    app_id = request.args.get('app_id', '').strip()
    gender = request.args.get('gender', '').strip()
    district_id = request.args.get('district_id', '').strip()

    query = Account.query.filter(Account.deleted_at.is_(None))
    if app_id:
        query = query.filter(Account.app_id == app_id)
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
        d = a.to_dict(include_private=True)
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
    'max_distance_km', 'photos', 'discoverability',
    # Every field the mobile dating wizard (profile_wizard_screen.dart)
    # actually collects — pets/love_languages/region_id were on the model
    # (DatingProfile.ATTRIBUTE_FIELDS) but missing here, so the admin console
    # could never set what a real member's own wizard can. See
    # AccountFormModal.jsx for the matching UI fields.
    'pets', 'love_languages', 'region_id',
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


def _clean_phone(raw):
    """Strip a pasted/typed phone number down to digits (keeping a leading
    + for the country code) — mirrors the same cleanup in
    AccountFormModal.jsx client-side; done again here so a non-UI caller of
    this API can't skip it and leave "+256 700-000 000" style values in the
    uniqueness index."""
    raw = (raw or '').strip()
    if not raw:
        return None
    has_plus = raw.startswith('+')
    digits = re.sub(r'\D', '', raw)
    if not digits:
        return None
    return ('+' if has_plus else '') + digits


def _apply_whitelisted_fields(instance, data, allowed_fields):
    for field in allowed_fields:
        if field in data:
            setattr(instance, field, data[field])


@admin_v1_bp.route('/accounts', methods=['POST'])
@_admin_required
def create_account_admin(account):
    """
    Admin-created account with an optional complete profile in one request.

    Body: display_name (required), phone (required), handle?, email?, password?,
    app_id? ('linkup'|'abanoonya'|'uganda_dating', default 'linkup'), is_premium?,
    account_status? (active|inactive|suspended|closed, default active),
    modes?: {professional?, sparks?}, dating_profile?: {...}, professional_profile?: {...}

    Phone is required — every account needs a way to log in, and phone is
    the primary identifier this app is built around; email stays optional.
    If password is omitted, one is generated
    and returned ONCE in this response's `generated_password` — never
    logged, never retrievable afterward (matches the project's standing rule
    against ever using a fixed/shared default password).
    """
    data = request.get_json(silent=True) or {}
    display_name = (data.get('display_name') or '').strip()
    phone = _clean_phone(data.get('phone'))
    email = (data.get('email') or '').strip().lower() or None
    handle = (data.get('handle') or '').strip().lower() or None

    if not display_name:
        return error_response('display_name is required.', status_code=400)
    if len(display_name) > 200:
        return error_response('display_name is too long (max 200 characters).', status_code=400)
    if not phone:
        return error_response('Phone number is required.', status_code=400)

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
    if app_id not in VALID_APP_IDS:
        return error_response(f'app_id must be one of: {", ".join(sorted(VALID_APP_IDS))}.', status_code=400)

    account_status = (data.get('account_status') or 'active').strip()
    if account_status not in _ACCOUNT_STATUSES:
        return error_response(f'account_status must be one of: {", ".join(_ACCOUNT_STATUSES)}')

    modes_in = data.get('modes') or {}
    modes_enabled = {
        'professional': bool(modes_in.get('professional', app_id not in DATING_ONLY_APP_IDS)),
        'sparks': bool(modes_in.get('sparks', app_id in DATING_ONLY_APP_IDS)),
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

    result = new_account.to_dict(include_private=True)
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
    Phone is required — this rejects clearing it (via phone: '') and, for a
    legacy account that somehow has none, rejects saving anything else until
    one is added.
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
        phone = _clean_phone(data.get('phone'))
        if phone and Account.query.filter(Account.phone == phone, Account.id != account_id).first():
            return error_response('An account with that phone number already exists.', status_code=400)
        target.phone = phone

    if 'email' in data:
        email = (data.get('email') or '').strip().lower() or None
        if email and Account.query.filter(Account.email == email, Account.id != account_id).first():
            return error_response('An account with that email already exists.', status_code=400)
        target.email = email

    if not target.phone:
        return error_response('Phone number is required.', status_code=400)

    if 'handle' in data:
        handle = (data.get('handle') or '').strip().lower()
        if handle and handle != target.handle:
            if Account.query.filter(Account.handle == handle, Account.id != account_id).first():
                return error_response('That handle is already taken.', status_code=400)
            target.handle = handle

    if 'app_id' in data:
        app_id = (data.get('app_id') or '').strip()
        if app_id not in VALID_APP_IDS:
            return error_response(f'app_id must be one of: {", ".join(sorted(VALID_APP_IDS))}.', status_code=400)
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
    return success_response('Account updated.', target.to_dict(include_private=True))


@admin_v1_bp.route('/accounts/<account_id>/photos', methods=['POST'])
@_admin_required
def upload_account_photo(account, account_id):
    """Upload one photo on behalf of a target account (multipart: field=photo
    or photo_url, plus optional is_profile_photo/is_cover_photo/is_public/
    caption form fields).

    Branches on Sparks mode because the mobile app itself does: a Sparks
    member's swipeable photos live in DatingProfile.photos (see
    sparks/routes.py:upload_dating_photo) — Account.avatar/UserPhoto is a
    completely separate store the deck never reads beyond a single-photo
    fallback. Before this branch, every admin-uploaded photo went through
    PhotoService (UserPhoto), so an admin dragging in 5 gallery photos for a
    dating profile produced exactly one photo the member's matches could
    ever see — an admin/mobile contradiction, not a deliberate limit.
    Professional-only accounts (no Sparks mode) keep using PhotoService
    unchanged, since that's genuinely where mobile puts their avatar/gallery
    too."""
    target = db.session.get(Account, account_id)
    if not target or target.deleted_at:
        return error_response('Account not found.', status_code=404)

    if target.modes.get('sparks', False):
        return _upload_dating_photo_admin(target)

    from backend.domains.photos.service import PhotoService
    return PhotoService.upload(target, request)


def _upload_dating_photo_admin(target):
    """Same storage + shape + 6-photo cap as sparks/routes.py's own
    upload_dating_photo/add_dating_photo — this is the admin-on-behalf-of
    twin of those two member-facing endpoints, not a separate reimplementation
    that could drift from them."""
    import uuid
    from backend.domains.profile.models import DatingProfile
    from backend.shared.storage.image_compress import compress_image
    from backend.shared.storage.r2 import save_bytes, save_upload
    from backend.shared.storage.url_fetch import fetch_image_from_url, ImageFetchError

    file = request.files.get('photo')
    photo_url = (request.form.get('photo_url') or '').strip()
    caption = (request.form.get('caption') or '').strip()[:200] or None

    dp = DatingProfile.query.filter_by(account_id=target.id).first()
    if not dp:
        dp = DatingProfile(id=str(uuid.uuid4()), account_id=target.id)
        db.session.add(dp)

    from backend.domains.sparks.routes import MAX_DATING_PHOTOS
    photos = list(dp.photos or [])
    if len(photos) >= MAX_DATING_PHOTOS:
        return error_response(f'Maximum {MAX_DATING_PHOTOS} photos allowed. Delete one first.')

    if file:
        url = save_upload(file, folder='dating_photos')
        if not url:
            return error_response('Upload failed. Use JPG, PNG, or WebP images.')
    elif photo_url:
        try:
            raw, _ = fetch_image_from_url(photo_url)
        except ImageFetchError as e:
            return error_response(str(e))
        try:
            compressed, ext = compress_image(raw)
        except ValueError:
            return error_response('Upload failed. Use JPG, PNG, or WebP images.')
        url = save_bytes(compressed, ext, folder='dating_photos')
        if not url:
            return error_response('Could not save that image.')
    else:
        return error_response('No photo file or photo_url provided.')

    photos.append({'url': url, 'caption': caption})
    dp.photos = photos
    db.session.commit()
    return success_response('Photo uploaded.', {'photos': dp.photos}, status_code=201)


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
    """Full account detail — everything about one member in one place: base
    account, professional + dating profile, wallet, KYC status, photo count,
    report history. This is what the account-detail page in the console reads;
    the bare account row alone isn't enough to act on a report or support case."""
    target = db.session.get(Account, account_id)
    if not target:
        return error_response('Account not found.', status_code=404)
    data = target.to_dict(include_private=True)
    data['report_count'] = Report.query.filter_by(target_account_id=account_id).count()
    data['reports_filed_count'] = Report.query.filter_by(reporter_id=account_id).count()

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

    try:
        from backend.domains.wallet.models import WalletAccount
        wallet = WalletAccount.query.filter_by(account_id=account_id).first()
        data['wallet'] = wallet.to_dict() if wallet else None
    except Exception:
        data['wallet'] = None

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

    try:
        from backend.domains.identity.models import Verification
        submissions = (Verification.query.filter_by(account_id=account_id)
                       .order_by(Verification.created_at.desc()).limit(5).all())
        data['kyc_submissions'] = [v.to_dict() for v in submissions]
    except Exception:
        data['kyc_submissions'] = []

    try:
        from backend.domains.safety.models import Block
        data['blocked_by_count'] = Block.query.filter_by(blocked_id=account_id).count()
        data['blocking_count'] = Block.query.filter_by(blocker_id=account_id).count()
    except Exception:
        data['blocked_by_count'] = 0
        data['blocking_count'] = 0

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
    from backend.domains.admin.models import log_admin_action
    log_admin_action(account.id, 'account.status', target_account_id=target.id,
                      detail={'status': new_status, 'reason': reason or None})
    db.session.commit()
    return success_response(f'Account status set to {new_status}.', target.to_dict(include_private=True))


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
    from backend.domains.admin.models import log_admin_action
    log_admin_action(account.id, 'account.premium', target_account_id=target.id,
                      detail={'is_premium': is_premium})
    db.session.commit()
    return success_response(
        f'Premium {"granted" if is_premium else "revoked"}.', target.to_dict(include_private=True)
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
        d['target'] = target.to_dict(include_private=True) if target else None
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


# ─── Wallet & Withdrawals ──────────────────────────────────────────────────────
# The one genuinely broken flow this console fixes: POST /v1/wallet/withdraw sets
# status='review' for any payout at/above the auto-limit and the code comment
# says "admin releases later" — but nothing ever listed or released one. Below is
# that release path.

@admin_v1_bp.route('/withdrawals', methods=['GET'])
@_admin_required
def list_withdrawals(account):
    """?status=requested|processing|paid|failed|reversed|review (omit for all)."""
    from backend.domains.wallet.models import Withdrawal
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', '').strip()
    query = Withdrawal.query
    if status:
        query = query.filter(Withdrawal.status == status)
    query = query.order_by(Withdrawal.requested_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    result = []
    for w in items:
        d = w.to_dict()
        acct = db.session.get(Account, w.account_id)
        d['account'] = {'id': acct.id, 'display_name': acct.display_name,
                        'handle': acct.handle} if acct else None
        result.append(d)
    return paginated_response(result, total, page, per_page, 'Withdrawals loaded.')


@admin_v1_bp.route('/withdrawals/<withdrawal_id>/release', methods=['PUT'])
@_admin_required
def release_withdrawal(account, withdrawal_id):
    """Release a review-status withdrawal for payout, or reject it (refunds the
    amount back to the member's wallet balance). This is the route that didn't
    exist — money sent to `review` had no way out before this."""
    from backend.domains.wallet.models import Withdrawal, WalletAccount, WalletTransaction
    w = db.session.get(Withdrawal, withdrawal_id)
    if not w:
        return error_response('Withdrawal not found.', status_code=404)
    if w.status != 'review':
        return error_response(f'Only review-status withdrawals can be released or rejected (current: {w.status}).')

    data = request.get_json(silent=True) or {}
    decision = (data.get('decision') or '').strip()  # 'approve' | 'reject'
    note = (data.get('note') or '').strip()

    if decision == 'approve':
        w.status = 'processing'
        w.failure_reason = None
    elif decision == 'reject':
        w.status = 'reversed'
        w.failure_reason = note or 'Rejected by admin review.'
        wallet = WalletAccount.query.filter_by(account_id=w.account_id).first()
        if wallet:
            wallet.balance = (wallet.balance or 0) + w.amount_ugx
            db.session.add(WalletTransaction(
                wallet_id=wallet.id, account_id=w.account_id, type='credit',
                category='withdrawal_reversal', amount=w.amount_ugx,
                balance_before=wallet.balance - w.amount_ugx, balance_after=wallet.balance,
                reference=w.flw_reference, description=note or 'Withdrawal rejected — refunded.',
            ))
    else:
        return error_response('decision must be: approve or reject')

    db.session.commit()

    try:
        from backend.domains.notifications.service import create_notification
        create_notification(
            account_id=w.account_id,
            notif_type='wallet.withdrawal_reviewed',
            title='Withdrawal approved' if decision == 'approve' else 'Withdrawal rejected',
            body=(f'Your withdrawal of {w.net_ugx:,.0f} UGX is being processed.' if decision == 'approve'
                  else f'Your withdrawal was rejected and refunded to your balance. {note}'.strip()),
            data={'withdrawal_id': w.id}, action_url='/wallet',
        )
    except Exception:
        pass

    return success_response(f'Withdrawal {w.status}.', w.to_dict())


@admin_v1_bp.route('/gifts', methods=['GET'])
@_admin_required
def list_gifts(account):
    """Platform-wide gift transaction ledger — revenue + abuse monitoring."""
    from backend.domains.wallet.models import Gift
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = Gift.query.order_by(Gift.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    result = []
    for g in items:
        d = g.to_dict()
        sender = db.session.get(Account, g.sender_id)
        recipient = db.session.get(Account, g.recipient_id)
        d['sender'] = {'display_name': sender.display_name, 'handle': sender.handle} if sender else None
        d['recipient'] = {'display_name': recipient.display_name, 'handle': recipient.handle} if recipient else None
        result.append(d)
    return paginated_response(result, total, page, per_page, 'Gifts loaded.')


@admin_v1_bp.route('/gift-catalog', methods=['GET'])
@_admin_required
def list_gift_catalog(account):
    """Full catalog including inactive items (member-facing /v1/gifts/catalog hides those)."""
    from backend.domains.wallet.models import GiftCatalog
    items = GiftCatalog.query.order_by(GiftCatalog.sort_order).all()
    result = [{**g.to_dict(), 'id': g.id, 'active': bool(g.active), 'sort_order': g.sort_order} for g in items]
    return success_response('Gift catalog loaded.', result)


@admin_v1_bp.route('/gift-catalog/<gift_id>', methods=['PUT'])
@_admin_required
def update_gift_catalog_item(account, gift_id):
    """Pricing lived in the DB only until now — name/price_coins/cash_value_ugx/active/sort_order."""
    from backend.domains.wallet.models import GiftCatalog
    g = db.session.get(GiftCatalog, gift_id)
    if not g:
        return error_response('Gift not found.', status_code=404)
    data = request.get_json(silent=True) or {}
    for field in ('name', 'icon'):
        if field in data:
            setattr(g, field, data[field])
    for field in ('price_coins', 'sort_order'):
        if field in data:
            setattr(g, field, int(data[field]))
    if 'cash_value_ugx' in data:
        g.cash_value_ugx = data['cash_value_ugx']
    if 'active' in data:
        g.active = 1 if data['active'] else 0
    db.session.commit()
    return success_response('Gift updated.', g.to_dict())


@admin_v1_bp.route('/gift-catalog', methods=['POST'])
@_admin_required
def create_gift_catalog_item(account):
    import uuid
    from backend.domains.wallet.models import GiftCatalog
    data = request.get_json(silent=True) or {}
    code = (data.get('code') or '').strip()
    name = (data.get('name') or '').strip()
    if not code or not name:
        return error_response('code and name are required.')
    if GiftCatalog.query.filter_by(code=code).first():
        return error_response('A gift with that code already exists.')
    g = GiftCatalog(
        id=str(uuid.uuid4()), code=code, name=name, icon=data.get('icon', '🎁'),
        price_coins=int(data.get('price_coins', 1)),
        cash_value_ugx=data.get('cash_value_ugx', 50),
        sort_order=int(data.get('sort_order', 999)), active=1,
    )
    db.session.add(g)
    db.session.commit()
    return success_response('Gift created.', g.to_dict(), status_code=201)


# ─── Safety: Panic Alerts & Blocks ─────────────────────────────────────────────

@admin_v1_bp.route('/panic-alerts', methods=['GET'])
@_admin_required
def list_panic_alerts(account):
    """?status=open|acknowledged|resolved (omit for all)."""
    from backend.domains.safety.models import PanicAlert
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', '').strip()
    query = PanicAlert.query
    if status:
        query = query.filter(PanicAlert.status == status)
    query = query.order_by(PanicAlert.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([p.to_dict() for p in items], total, page, per_page, 'Panic alerts loaded.')


@admin_v1_bp.route('/panic-alerts/<alert_id>/resolve', methods=['PUT'])
@_admin_required
def resolve_panic_alert(account, alert_id):
    from backend.domains.safety.models import PanicAlert
    alert = db.session.get(PanicAlert, alert_id)
    if not alert:
        return error_response('Panic alert not found.', status_code=404)
    data = request.get_json(silent=True) or {}
    new_status = (data.get('status') or 'resolved').strip()
    if new_status not in ('acknowledged', 'resolved'):
        return error_response('status must be: acknowledged or resolved')
    alert.status = new_status
    alert.resolved_by = account.id
    alert.resolved_at = datetime.utcnow()
    alert.resolution_note = (data.get('note') or '').strip() or None
    db.session.commit()
    return success_response(f'Panic alert {new_status}.', alert.to_dict())


@admin_v1_bp.route('/blocks', methods=['GET'])
@_admin_required
def list_blocks(account):
    """All member-to-member blocks — a pattern of many people blocking one
    account is a real abuse signal that was previously invisible to admins."""
    from backend.domains.safety.models import Block
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = Block.query.order_by(Block.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    result = []
    for b in items:
        blocker = db.session.get(Account, b.blocker_id)
        result.append({
            'id': b.id,
            'blocker': {'id': blocker.id, 'display_name': blocker.display_name,
                        'handle': blocker.handle} if blocker else None,
            'blocked': b.blocked.to_dict() if b.blocked else None,
            'created_at': b.created_at.isoformat() if b.created_at else None,
        })
    return paginated_response(result, total, page, per_page, 'Blocks loaded.')


@admin_v1_bp.route('/blocks/most-blocked', methods=['GET'])
@_admin_required
def most_blocked_accounts(account):
    """Accounts blocked by the most distinct people — abuse-pattern surfacing."""
    from backend.domains.safety.models import Block
    rows = (db.session.query(Block.blocked_id, func.count(Block.id).label('cnt'))
            .group_by(Block.blocked_id).order_by(func.count(Block.id).desc()).limit(20).all())
    result = []
    for blocked_id, cnt in rows:
        acct = db.session.get(Account, blocked_id)
        if acct:
            result.append({'account': {'id': acct.id, 'display_name': acct.display_name,
                                       'handle': acct.handle}, 'block_count': cnt})
    return success_response('Most-blocked accounts loaded.', result)


# ─── KYC Review Queue ──────────────────────────────────────────────────────────

@admin_v1_bp.route('/kyc', methods=['GET'])
@_admin_required
def list_kyc_submissions(account):
    """?status=pending|approved|rejected (default pending). Includes the
    submitted ID photo + selfie URLs so this is a real visual review, not a
    blind rubber-stamp on a self-reported ID number string."""
    from backend.domains.identity.models import Verification

    status = request.args.get('status', 'pending').strip()
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    query = Verification.query.filter_by(status=status).order_by(Verification.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)

    account_ids = [v.account_id for v in items]
    accounts = {a.id: a for a in Account.query.filter(Account.id.in_(account_ids)).all()} if account_ids else {}

    result = []
    for v in items:
        acct = accounts.get(v.account_id)
        d = v.to_dict()
        d['account'] = ({'id': acct.id, 'display_name': acct.display_name, 'handle': acct.handle,
                         'kyc_level': acct.kyc_level} if acct else None)
        result.append(d)
    return paginated_response(result, total, page, per_page, 'KYC submissions loaded.')


@admin_v1_bp.route('/kyc/<submission_id>/decide', methods=['PUT'])
@_admin_required
def decide_kyc(account, submission_id):
    """Approve bumps the account to KYC L3 (fully verified); reject rolls them
    back to L1 so they can resubmit, optionally with a reason the member sees
    on their own account payload (identity/routes.py's _latest_verification_dict)."""
    from backend.domains.identity.models import Verification

    data = request.get_json(silent=True) or {}
    decision = (data.get('decision') or '').strip()
    reason = (data.get('reason') or '').strip()[:500] or None
    if decision not in ('approve', 'reject'):
        return error_response('decision must be: approve or reject')

    submission = db.session.get(Verification, submission_id)
    if not submission:
        return error_response('Submission not found.', status_code=404)

    new_status = 'approved' if decision == 'approve' else 'rejected'
    submission.status = new_status
    submission.reviewed_by = account.id
    if decision == 'approve':
        submission.verified_at = datetime.utcnow()
    else:
        submission.rejection_reason = reason

    target = db.session.get(Account, submission.account_id)
    if target:
        target.kyc_level = 3 if decision == 'approve' else 1
    from backend.domains.admin.models import log_admin_action
    log_admin_action(account.id, 'kyc.decide', target_account_id=submission.account_id,
                      detail={'decision': decision, 'reason': reason})
    db.session.commit()

    try:
        from backend.domains.notifications.service import create_notification
        create_notification(
            account_id=submission.account_id, notif_type='admin.kyc_reviewed',
            title='Verification approved' if decision == 'approve' else 'Verification rejected',
            body=('Your identity is fully verified.' if decision == 'approve'
                  else (f'Your ID submission was rejected — {reason}' if reason
                        else 'Your ID submission was rejected — please resubmit.')),
            action_url='/settings',
        )
    except Exception:
        pass

    return success_response(f'KYC {new_status}.', {'account_id': submission.account_id, 'status': new_status})


# ─── Institution Approval Queue ────────────────────────────────────────────────

@admin_v1_bp.route('/institutions', methods=['GET'])
@_admin_required
def list_institutions_admin(account):
    """?verified=0|1 (default 0 — the review queue)."""
    from backend.domains.reference.models import Institution
    verified = request.args.get('verified', '0', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = Institution.query.filter_by(verified=verified).order_by(Institution.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([i.to_dict() for i in items], total, page, per_page, 'Institutions loaded.')


@admin_v1_bp.route('/institutions/<institution_id>/verify', methods=['PUT'])
@_admin_required
def verify_institution(account, institution_id):
    """Approve a user-suggested institution, or reject (deletes it — it was
    never a real reference entry to begin with)."""
    from backend.domains.reference.models import Institution
    inst = db.session.get(Institution, institution_id)
    if not inst:
        return error_response('Institution not found.', status_code=404)
    data = request.get_json(silent=True) or {}
    decision = (data.get('decision') or '').strip()
    if decision == 'approve':
        inst.verified = 1
        db.session.commit()
        return success_response('Institution approved.', inst.to_dict())
    elif decision == 'reject':
        db.session.delete(inst)
        db.session.commit()
        return success_response('Institution rejected and removed.', {'id': institution_id})
    return error_response('decision must be: approve or reject')


# ─── App Version / Force-Update Config ─────────────────────────────────────────

@admin_v1_bp.route('/app-versions', methods=['GET'])
@_admin_required
def list_app_versions(account):
    from backend.domains.app_version.models import AppVersion
    rows = AppVersion.query.order_by(AppVersion.app_id, AppVersion.platform).all()
    return success_response('App version config loaded.', [
        {'id': r.id, 'app_id': r.app_id, 'platform': r.platform, 'latest_build': r.latest_build,
         'latest_version_name': r.latest_version_name, 'min_supported_build': r.min_supported_build,
         'update_notes': r.update_notes, 'android_url': r.android_url, 'ios_url': r.ios_url,
         'updated_at': r.updated_at.isoformat() if r.updated_at else None}
        for r in rows
    ])


@admin_v1_bp.route('/app-versions/<row_id>', methods=['PUT'])
@_admin_required
def update_app_version(account, row_id):
    """Ship a build, bump min_supported_build to force everyone onto it. This
    was DB-only before — the read endpoint (GET /v1/app/version) existed but
    nothing could write these 4 rows without touching the database directly."""
    from backend.domains.app_version.models import AppVersion
    row = db.session.get(AppVersion, row_id)
    if not row:
        return error_response('Config row not found.', status_code=404)
    data = request.get_json(silent=True) or {}
    for field in ('latest_build', 'min_supported_build'):
        if field in data:
            setattr(row, field, int(data[field]))
    for field in ('latest_version_name', 'update_notes', 'android_url', 'ios_url'):
        if field in data:
            setattr(row, field, data[field])
    db.session.commit()
    return success_response('App version config updated.', {
        'id': row.id, 'app_id': row.app_id, 'platform': row.platform,
        'latest_build': row.latest_build, 'min_supported_build': row.min_supported_build,
    })


# ─── Subscription Plans & Subscribers (Phase 5) ────────────────────────────────
# Mirrors the gift-catalog CRUD pattern above (list-all-including-inactive,
# db.session.get + 404, per-field `if field in data: setattr(...)` on PUT,
# uniqueness check + uuid + 201 on POST).

@admin_v1_bp.route('/subscription-plans', methods=['GET'])
@_admin_required
def list_subscription_plans(account):
    """Full plan catalog including inactive plans (member-facing
    /v1/subscriptions/plans hides those — admin needs to see everything).
    ?app_id= filters to one brand; omit for both."""
    app_id = request.args.get('app_id', '').strip()
    query = SubscriptionPlan.query
    if app_id:
        query = query.filter(SubscriptionPlan.app_id == app_id)
    query = query.order_by(SubscriptionPlan.app_id, SubscriptionPlan.sort_order)
    items = query.all()
    return success_response('Subscription plans loaded.', [p.to_dict() for p in items])


@admin_v1_bp.route('/subscription-plans', methods=['POST'])
@_admin_required
def create_subscription_plan(account):
    """Body: app_id, code, name, tagline?, price_ugx, duration_days, sort_order?,
    badge_color?, limits (dict, persisted as-is — the column is JSON). active
    defaults to 1. (app_id, code) must be unique (matches the DB's
    uq_plan_app_code constraint)."""
    import uuid
    data = request.get_json(silent=True) or {}
    app_id = (data.get('app_id') or '').strip()
    code = (data.get('code') or '').strip()
    name = (data.get('name') or '').strip()
    if not app_id or not code or not name:
        return error_response('app_id, code and name are required.')
    if SubscriptionPlan.query.filter_by(app_id=app_id, code=code).first():
        return error_response('A plan with that code already exists for this app.')

    plan = SubscriptionPlan(
        id=str(uuid.uuid4()),
        app_id=app_id,
        code=code,
        name=name,
        tagline=(data.get('tagline') or '').strip() or None,
        price_ugx=data.get('price_ugx', 0),
        duration_days=int(data.get('duration_days', 0)),
        sort_order=int(data.get('sort_order', 0)),
        badge_color=(data.get('badge_color') or '').strip() or None,
        limits=data.get('limits') or {},
        active=1,
    )
    db.session.add(plan)
    db.session.commit()
    return success_response('Subscription plan created.', plan.to_dict(), status_code=201)


@admin_v1_bp.route('/subscription-plans/<plan_id>', methods=['PUT'])
@_admin_required
def update_subscription_plan(account, plan_id):
    """Update any subset of: name, tagline, price_ugx, duration_days, sort_order,
    active, badge_color, limits, discount_price_ugx, discount_ends_at.
    app_id/code are the row's identity and are not editable here."""
    plan = db.session.get(SubscriptionPlan, plan_id)
    if not plan:
        return error_response('Subscription plan not found.', status_code=404)

    data = request.get_json(silent=True) or {}
    for field in ('name', 'tagline', 'badge_color'):
        if field in data:
            setattr(plan, field, data[field])
    if 'price_ugx' in data:
        plan.price_ugx = data['price_ugx']
    if 'duration_days' in data:
        plan.duration_days = int(data['duration_days'])
    if 'sort_order' in data:
        plan.sort_order = int(data['sort_order'])
    if 'active' in data:
        plan.active = 1 if data['active'] else 0
    if 'limits' in data:
        plan.limits = data['limits'] or {}
    if 'discount_price_ugx' in data:
        plan.discount_price_ugx = data['discount_price_ugx']
    if 'discount_ends_at' in data:
        raw = (data['discount_ends_at'] or '').strip() if isinstance(data['discount_ends_at'], str) else data['discount_ends_at']
        if not raw:
            plan.discount_ends_at = None
        else:
            try:
                plan.discount_ends_at = datetime.fromisoformat(raw.replace('Z', '+00:00')).replace(tzinfo=None)
            except (ValueError, AttributeError):
                return error_response('discount_ends_at must be a valid ISO datetime string, or null to clear it.')

    db.session.commit()
    return success_response('Subscription plan updated.', plan.to_dict())


@admin_v1_bp.route('/subscriptions', methods=['GET'])
@_admin_required
def list_subscriptions(account):
    """Subscriber list — flat, admin-friendly rows joining Account (member
    identity) + SubscriptionPlan (plan name/price). ?status=&app_id=&page=&per_page=.
    Also returns a revenue_summary alongside the paginated list: active
    subscriber count + total revenue from active subscriptions."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', '').strip()
    app_id = request.args.get('app_id', '').strip()

    query = Subscription.query.join(Account, Subscription.account_id == Account.id)
    if status:
        query = query.filter(Subscription.status == status)
    if app_id:
        query = query.filter(Account.app_id == app_id)
    query = query.order_by(Subscription.created_at.desc())

    items, total, page, last_page, per_page = paginate_query(query, page, per_page)

    def _row(s):
        acct = db.session.get(Account, s.account_id)
        plan = db.session.get(SubscriptionPlan, s.plan_id)
        return {
            'id': s.id,
            'account': {'id': acct.id, 'display_name': acct.display_name,
                        'handle': acct.handle, 'phone': acct.phone} if acct else None,
            'plan': {'name': plan.name, 'code': plan.code,
                     'price_ugx': float(plan.price_ugx)} if plan else None,
            'status': s.status,
            'starts_at': s.starts_at.isoformat() if s.starts_at else None,
            'expires_at': s.expires_at.isoformat() if s.expires_at else None,
            'amount_paid_ugx': float(s.amount_paid_ugx or 0),
            'created_at': s.created_at.isoformat() if s.created_at else None,
        }

    revenue_query = Subscription.query.join(Account, Subscription.account_id == Account.id) \
        .filter(Subscription.status == 'active')
    if app_id:
        revenue_query = revenue_query.filter(Account.app_id == app_id)
    total_active_subscribers = revenue_query.count()
    total_revenue_ugx = revenue_query.with_entities(
        func.coalesce(func.sum(Subscription.amount_paid_ugx), 0)
    ).scalar() or 0

    payload = {
        'current_page': page,
        'data': [_row(s) for s in items],
        'per_page': per_page,
        'total': total,
        'last_page': last_page,
        'revenue_summary': {
            'total_active_subscribers': total_active_subscribers,
            'total_revenue_ugx': float(total_revenue_ugx),
        },
    }
    return success_response('Subscriptions loaded.', payload)
