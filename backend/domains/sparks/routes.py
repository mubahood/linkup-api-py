"""
Sparks routes: /v1/sparks/*
Mode-protected: account must have sparks enabled.
"""
import uuid
from flask import Blueprint, request
from sqlalchemy import or_
from backend.models import db
from backend.domains.sparks.models import Spark, Match
from backend.domains.sparks.service import (
    get_deck, record_action, search_people, get_trending_cards,
    get_profile_card, get_match_with,
)
from backend.domains.subscriptions import service as sub_service
from backend.shared.auth.decorators import sparks_mode_required, lu_jwt_required
from backend.shared.idempotency import idempotent
from backend.shared.ratelimit import rate_limit
from backend.shared.utils.response import success_response, error_response, paginated_response
from backend.shared.utils.pagination import paginate_query

sparks_bp = Blueprint('v1_sparks', __name__, url_prefix='/v1/sparks')

# Single source of truth for the dating-photos cap — matches the mobile
# wizard's own limit (lu_wizard.dart) and the admin console's photo-slot UI
# (AccountFormModal.jsx's PHOTO_SLOTS), and is imported by admin/routes.py's
# mirror of these two endpoints so all three never drift out of sync again.
MAX_DATING_PHOTOS = 10

# Free previews shown to an account before its dating profile is complete —
# matches sparks_screen.dart's _maxFreeSwipes. That client-side counter
# resets to 0 on every app restart (it's just a local `int`), so it was only
# ever a UX nicety, not real enforcement — an incomplete profile could get
# unlimited free previews by force-closing and reopening the app. This
# constant backs the server-side check in action() below, which counts
# lifetime Spark rows (never reset by a restart) and is the real gate.
MAX_FREE_PREVIEW_SWIPES = 3


def _profile_gate_incomplete(account) -> bool:
    """Mirrors sparks_screen.dart's _loadProfilingStatus() definition of a
    'complete enough to swipe freely' profile — kept in sync by hand since
    there's no shared schema between the two. If this ever drifts, the
    server becomes stricter than the client, not looser (fails closed)."""
    from backend.domains.profile.models import DatingProfile
    dp = DatingProfile.query.filter_by(account_id=account.id).first()
    if not dp:
        return True
    about_done = bool((dp.bio or '').strip()) or (dp.gender is not None and dp.birth_year is not None)
    prefs = dp.preferences if isinstance(dp.preferences, dict) else None
    looking_done = dp.looking_for_gender is not None or dp.age_min is not None or bool(prefs)
    return not (about_done and looking_done)


def _norm_gender(v):
    """Canonicalise any gender input to the only two app-wide values: male/female.
    Accepts the man/woman vocabulary too. Returns None if unresolvable so the
    caller can reject it — gender is never stored as anything but male/female."""
    g = (v or '').lower().strip()
    g = {'man': 'male', 'woman': 'female', 'm': 'male',
         'f': 'female', 'w': 'female'}.get(g, g)
    return g if g in ('male', 'female') else None


@sparks_bp.route('/deck', methods=['GET'])
@sparks_mode_required
def deck(account):
    """
    Get discovery deck.
    ?refresh=true — include previously-passed profiles (deck re-discovery).
    Auto-refresh: if the fresh deck is empty but there are passed profiles to recycle,
    automatically include them so the deck never shows empty due to exhaustion.
    """
    limit = request.args.get('limit', 20, type=int)
    refresh = request.args.get('refresh', '').lower() == 'true'
    max_distance_km = request.args.get('max_distance_km', None, type=float)

    def _csv(name):
        raw = (request.args.get(name) or '').strip()
        return [v.strip().lower() for v in raw.split(',') if v.strip()] if raw else None

    filters = {
        'genders': _csv('gender'),          # candidate gender(s)
        'intents': _csv('intent'),          # casual / serious / …
        'drinking': _csv('drinking'),
        'smoking': _csv('smoking'),
        'age_min': request.args.get('age_min', None, type=int),
        'age_max': request.args.get('age_max', None, type=int),
        'country_code': (request.args.get('country_code') or '').strip().upper() or None,
        'region_id': (request.args.get('region_id') or '').strip() or None,
        'has_photos': (request.args.get('has_photos') or '').lower() == 'true',
        'verified_only': (request.args.get('verified') or '').lower() == 'true',
    }

    cards = get_deck(account.id, limit=limit, allow_passed=refresh,
                     max_distance_km=max_distance_km, filters=filters)

    # Auto-refresh: deck exhausted but not explicitly refreshed yet
    if not cards and not refresh:
        from backend.domains.sparks.models import Spark
        has_passed = Spark.query.filter_by(
            actor_id=account.id, action='pass'
        ).first()
        if has_passed:
            cards = get_deck(account.id, limit=limit, allow_passed=True,
                             max_distance_km=max_distance_km, filters=filters)
            if cards:
                return success_response('Deck refreshed — showing previously passed profiles.', cards)

    return success_response('Deck loaded.', cards)


@sparks_bp.route('/trending', methods=['GET'])
@sparks_mode_required
def trending(account):
    """Coarse "Trending near you" cards — never a score/rank, a randomized
    sample of the current trending pool (see sparks/service.py:get_trending_cards
    for why: raw popularity numbers on a dating profile invite gaming)."""
    limit = min(request.args.get('limit', 10, type=int), 20)
    cards = get_trending_cards(account.id, account.app_id, limit=limit)
    return success_response('Trending loaded.', cards)


@sparks_bp.route('/notification-candidate', methods=['GET'])
@sparks_mode_required
def notification_candidate(account):
    """One discovery-deck candidate for the "browse from the notification
    shade" feature — same ranking/safety-exclusion pipeline as /deck (reused
    via get_deck's extra_excluded param), sliced to a single lightweight
    card instead of a full swipe deck. ?exclude=id1,id2,... lets the client
    skip whoever it's already shown this Next-cycling session. data: null
    when nothing's left to show."""
    from backend.domains.notifications.service import resolve_image_url

    raw_exclude = (request.args.get('exclude') or '').strip()
    exclude_ids = {v.strip() for v in raw_exclude.split(',') if v.strip()}

    cards = get_deck(account.id, limit=1, extra_excluded=exclude_ids)
    if not cards:
        return success_response('No more candidates right now.', None)

    card = cards[0]
    dp = card.get('dating_profile') or {}
    photos = card.get('photos') or []
    photo_url = photos[0]['url'] if photos and photos[0].get('url') else None
    return success_response('Candidate loaded.', {
        'id': card['id'],
        'display_name': card.get('display_name'),
        'age': dp.get('age'),
        'location_label': dp.get('location_label'),
        'photo_url': resolve_image_url(photo_url),
    })


@sparks_bp.route('/profile-card/<account_id>', methods=['GET'])
@sparks_mode_required
def profile_card(account, account_id):
    """Full single-target profile card for the dating profile-detail screen
    — the same shape /deck cards use (dating_profile, photos, interest_tags,
    compatibility_pct, why, mutual_pct), just for one already-known account
    instead of a fresh ranked pool. Reached from a notification tap,
    profile-viewers, search results, or the swipe deck's "View full
    profile" button — all contexts that already have the target id."""
    card = get_profile_card(account.id, account_id)
    if not card:
        return error_response('Profile not found.', status_code=404)
    return success_response('Profile loaded.', card)


@sparks_bp.route('/matches/with/<target_id>', methods=['GET'])
@sparks_mode_required
def match_with(account, target_id):
    """Is the current account matched with target_id? Backs the profile-
    detail screen's context-aware action bar: matched → 'Open Chat' into
    the existing thread; not matched → the usual swipe actions."""
    return success_response('Match status loaded.', get_match_with(account.id, target_id))


@sparks_bp.route('/search', methods=['GET'])
@sparks_mode_required
def people_search(account):
    """Ranked people search by preference compatibility (unlimited, paginated).

    ?direction=outgoing → people I'm searching for (match my preferences)
    ?direction=incoming → people searching for me (I match their preferences)
    ?page, ?per_page    → delivery paging only; the full pool is ranked first.
    """
    direction = (request.args.get('direction') or 'outgoing').strip().lower()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 30, type=int)
    data = search_people(str(account.id), direction=direction,
                         page=page, per_page=per_page)
    return success_response('People loaded.', data)


@sparks_bp.route('/action', methods=['POST'])
@sparks_mode_required
@idempotent
@rate_limit(60, 60)  # 60 swipes / minute (T-API-071)
def action(account):
    """Record a swipe action."""
    data = request.get_json(silent=True) or {}
    target_id = data.get('target_id', '').strip()
    act = data.get('action', '').strip()

    if not target_id or not act:
        return error_response('target_id and action are required.')
    if act not in ('spark_up', 'pass', 'standout', 'undo'):
        return error_response('Invalid action. Use: spark_up, pass, standout, undo.')
    if target_id == account.id:
        return error_response('You cannot spark yourself.')

    quota = None
    if act in ('spark_up', 'pass', 'standout'):
        if _profile_gate_incomplete(account):
            # Lifetime count, not a daily one — this is a one-time onboarding
            # nudge, not a quota, and must survive an app restart (see
            # MAX_FREE_PREVIEW_SWIPES above).
            free_used = Spark.query.filter(
                Spark.actor_id == account.id,
                Spark.action.in_(('spark_up', 'pass', 'standout')),
            ).count()
            if free_used >= MAX_FREE_PREVIEW_SWIPES:
                return error_response(
                    'Finish your profile to keep swiping.', status_code=403,
                    data={'reason': 'profile_incomplete_gate'})

        today_start = sub_service.today_start()
        if act == 'standout':
            quota = sub_service.check_and_consume(
                account, 'standouts_per_day',
                lambda: Spark.query.filter(
                    Spark.actor_id == account.id, Spark.action == 'standout',
                    Spark.created_at >= today_start,
                ).count())
        else:
            quota = sub_service.check_and_consume(
                account, 'swipes_per_day',
                lambda: Spark.query.filter(
                    Spark.actor_id == account.id,
                    Spark.action.in_(('spark_up', 'pass')),
                    Spark.created_at >= today_start,
                ).count())
        if not quota['allowed']:
            return error_response(
                'Daily limit reached. Upgrade to keep swiping.', status_code=402,
                data={'used': quota['used'], 'limit': quota['limit'], 'upsell': True,
                      'reset_at': quota.get('reset_at')})

    spark, match = record_action(account.id, target_id, act)

    # Behavioral signal (T-API-053)
    from backend.shared.events.emit import emit
    emit(f'spark.{act}', account_id=account.id, object_type='account', object_id=target_id,
         context={'is_match': bool(match)})

    # First-match milestone: a one-shot bonus standout for whichever party
    # this was their first-ever match (each side checked independently).
    if match:
        for party_id in (account.id, target_id):
            party_match_count = Match.query.filter(
                or_(Match.account_a_id == party_id, Match.account_b_id == party_id),
            ).count()
            if party_match_count == 1:
                from backend.domains.identity.models import Account as _Account
                party = db.session.get(_Account, party_id)
                if party:
                    sub_service.grant_first_match_bonus(party)

    # Notify on match
    if match:
        try:
            from backend.domains.notifications.service import create_notification, photo_for_account
            from backend.domains.identity.models import Account
            actor_acct = Account.query.get(account.id)
            target_acct = Account.query.get(target_id)
            if actor_acct and target_acct:
                # A match is mutual — both parties already see each other on
                # the deck, so showing the other person's actual photo here
                # is safe (unlike an unmatched like/standout below, which
                # stays deliberately anonymized).
                for notif_target, other_name, other_id in [
                    (account.id, target_acct.display_name, target_id),
                    (target_id, actor_acct.display_name, account.id),
                ]:
                    create_notification(
                        account_id=notif_target,
                        notif_type='spark.match',
                        title=f"You matched with {other_name}! 🎉",
                        body="Say hello — don't be shy.",
                        data={'match_id': match.id},
                        action_url=f'/sparks/matches/{match.id}',
                        image_url=photo_for_account(other_id),
                    )
        except Exception:
            pass
    # Notify on an unmatched like/standout — a teaser, no identity revealed, to
    # drive the recipient back into the app to see who. Throttled to at most
    # once per 3 hours per recipient so a popular profile isn't spammed with a
    # push for every single incoming like.
    elif act in ('spark_up', 'standout'):
        try:
            from datetime import datetime, timedelta
            from backend.domains.notifications.models import Notification
            from backend.domains.notifications.service import create_notification
            recent_cutoff = datetime.utcnow() - timedelta(hours=3)
            recent = Notification.query.filter(
                Notification.account_id == target_id,
                Notification.type == 'spark.like',
                Notification.created_at > recent_cutoff,
            ).first()
            if not recent:
                create_notification(
                    account_id=target_id,
                    notif_type='spark.like',
                    title='Someone likes you 👀',
                    body='Open Abanoonya Pro to see who.',
                    action_url='/sparks/likes',
                )
        except Exception:
            pass

    quota_out = None
    if quota:
        # quota was checked before this action was recorded — reflect the
        # post-action state to the client rather than the stale pre-action one.
        remaining = quota['remaining'] if quota['remaining'] == -1 else max(0, quota['remaining'] - 1)
        quota_out = {'remaining': remaining, 'limit': quota['limit']}
        if quota.get('bonus'):
            quota_out['bonus'] = quota['bonus']
        if remaining <= 1 and remaining != -1:
            quota_out['nudge'] = f'{remaining} left today — upgrade for unlimited.'

    return success_response(
        "It's a match! 🎉" if match else 'Action recorded.',
        {
            'spark': spark.to_dict(),
            'match': match.to_dict(account.id) if match else None,
            'is_match': bool(match),
            'quota': quota_out,
        }
    )


@sparks_bp.route('/matches', methods=['GET'])
@sparks_mode_required
def matches(account):
    """List all matches."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = Match.query.filter(
        or_(Match.account_a_id == account.id, Match.account_b_id == account.id)
    ).order_by(Match.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    from backend.shared.utils.response import EMPTY_STATES
    return paginated_response([m.to_dict(account.id) for m in items], total, page, per_page,
                              'Matches loaded.', empty_state=EMPTY_STATES['matches'])


@sparks_bp.route('/matches/<match_id>/unmatch', methods=['POST'])
@sparks_mode_required
def unmatch(account, match_id):
    """Unmatch — ends the match and removes from each other's matches list."""
    match = Match.query.filter(
        Match.id == match_id,
        or_(Match.account_a_id == account.id, Match.account_b_id == account.id),
        Match.state == 'active',
    ).first()
    if not match:
        return error_response('Active match not found.', status_code=404)
    from datetime import datetime
    match.state = 'unmatched'
    match.unmatched_by = account.id
    match.unmatched_at = datetime.utcnow()
    db.session.commit()
    # Notify the other person
    other_id = match.account_b_id if account.id == match.account_a_id else match.account_a_id
    try:
        from backend.domains.notifications.service import create_notification
        create_notification(
            account_id=other_id,
            notif_type='spark.unmatched',
            title='You have been unmatched',
            body='This match is no longer active.',
            data={'match_id': match_id},
            action_url='/sparks/matches',
        )
    except Exception:
        pass
    return success_response('Unmatched successfully.')


@sparks_bp.route('/matches/<match_id>/met', methods=['POST'])
@sparks_mode_required
def mark_met(account, match_id):
    """Signal that you met this person in real life — ML outcome feedback."""
    match = Match.query.filter(
        Match.id == match_id,
        or_(Match.account_a_id == account.id, Match.account_b_id == account.id),
        Match.state == 'active',
    ).first()
    if not match:
        return error_response('Active match not found.', status_code=404)
    from datetime import datetime
    if not match.met_at:
        match.met_at = datetime.utcnow()
        db.session.commit()
    return success_response('Meeting recorded.', match.to_dict(account.id))


@sparks_bp.route('/matches/<match_id>', methods=['GET'])
@sparks_mode_required
def match_detail(account, match_id):
    match = Match.query.filter(
        Match.id == match_id,
        or_(Match.account_a_id == account.id, Match.account_b_id == account.id)
    ).first()
    if not match:
        return error_response('Match not found.', status_code=404)
    return success_response('Match loaded.', match.to_dict(account.id))


@sparks_bp.route('/matches/<match_id>/contact', methods=['GET'])
@lu_jwt_required
def match_contact(account, match_id):
    """Reveal the matched member's phone/WhatsApp number. Requires an active
    match the caller is actually a party to (never trust a client-supplied
    target id), the can_reveal_contact entitlement, AND a free slot in
    today's contacts_per_day quota — contact is only ever revealed between
    two people who already mutually liked each other, and only as often as
    their plan allows."""
    match = Match.query.filter(
        Match.id == match_id,
        or_(Match.account_a_id == account.id, Match.account_b_id == account.id),
        Match.state == 'active',
    ).first()
    if not match:
        return error_response('Match not found.', status_code=404,
                              data={'reason': 'not_matched'})
    if not sub_service.can(account, 'can_reveal_contact'):
        return error_response('Upgrade to reveal contact details.', status_code=403,
                              data={'reason': 'upgrade_required'})

    from backend.shared.events.models import BehavioralEvent
    today_start = sub_service.today_start()
    quota = sub_service.check_and_consume(
        account, 'contacts_per_day',
        lambda: BehavioralEvent.query.filter(
            BehavioralEvent.account_id == account.id,
            BehavioralEvent.verb == 'contact.reveal',
            BehavioralEvent.created_at >= today_start,
        ).count())
    if not quota['allowed']:
        return error_response(
            "You've used today's contact reveals. Upgrade for more.", status_code=402,
            data={'used': quota['used'], 'limit': quota['limit'], 'upsell': True,
                  'reset_at': quota.get('reset_at')})

    from backend.domains.identity.models import Account
    other_id = match.account_b_id if match.account_a_id == account.id else match.account_a_id
    other = db.session.get(Account, other_id)
    if not other:
        return error_response('Match not found.', status_code=404)

    from backend.shared.events.emit import emit
    emit('contact.reveal', account_id=account.id, object_type='account', object_id=other.id,
         context={'match_id': match.id})

    return success_response('Contact revealed.', {
        'account_id': other.id,
        'display_name': other.display_name,
        'phone': other.phone,
        'whatsapp': other.phone,
    })


@sparks_bp.route('/contact/<target_id>', methods=['GET'])
@lu_jwt_required
def browse_contact(account, target_id):
    """Reveal a browsed (not-yet-matched) profile's phone/WhatsApp number.
    Same gating as match_contact — the can_reveal_contact entitlement and a
    free slot in today's shared contacts_per_day quota — just without the
    active-match precondition, since this is called from the pre-match
    profile detail sheet. Blocked/heavily-reported accounts are excluded
    either direction, same as the deck and trending pool."""
    if target_id == account.id:
        return error_response('Invalid target.', status_code=400)

    from backend.domains.identity.models import Account
    from backend.domains.safety.models import Block, Report
    from sqlalchemy import func as _func, or_ as _or

    is_blocked = db.session.query(Block.id).filter(
        _or(
            (Block.blocker_id == account.id) & (Block.blocked_id == target_id),
            (Block.blocker_id == target_id) & (Block.blocked_id == account.id),
        )
    ).first()
    if is_blocked:
        return error_response('Contact not found.', status_code=404)

    report_count = db.session.query(_func.count(Report.id)).filter(
        Report.target_account_id == target_id
    ).scalar() or 0
    if report_count >= 3:
        return error_response('Contact not found.', status_code=404)

    other = Account.query.filter(
        Account.id == target_id,
        Account.account_status == 'active',
        Account.deleted_at.is_(None),
    ).first()
    if not other:
        return error_response('Contact not found.', status_code=404)

    if not sub_service.can(account, 'can_reveal_contact'):
        return error_response('Upgrade to reveal contact details.', status_code=403,
                              data={'reason': 'upgrade_required'})

    from backend.shared.events.models import BehavioralEvent
    today_start = sub_service.today_start()
    quota = sub_service.check_and_consume(
        account, 'contacts_per_day',
        lambda: BehavioralEvent.query.filter(
            BehavioralEvent.account_id == account.id,
            BehavioralEvent.verb == 'contact.reveal',
            BehavioralEvent.created_at >= today_start,
        ).count())
    if not quota['allowed']:
        return error_response(
            "You've used today's contact reveals. Upgrade for more.", status_code=402,
            data={'used': quota['used'], 'limit': quota['limit'], 'upsell': True,
                  'reset_at': quota.get('reset_at')})

    from backend.shared.events.emit import emit
    emit('contact.reveal', account_id=account.id, object_type='account', object_id=other.id,
         context={'pre_match': True})

    return success_response('Contact revealed.', {
        'account_id': other.id,
        'display_name': other.display_name,
        'phone': other.phone,
        'whatsapp': other.phone,
    })


# ─── Dating Profile ───────────────────────────────────────────────────────────

@sparks_bp.route('/profile', methods=['GET'])
@lu_jwt_required
def get_dating_profile(account):
    """Get my dating profile (preferences, bio, discoverability)."""
    from backend.domains.profile.models import DatingProfile
    dp = DatingProfile.query.filter_by(account_id=account.id).first()
    if not dp:
        return success_response('No dating profile yet.', None)
    return success_response('Dating profile loaded.', dp.to_dict())


@sparks_bp.route('/profile', methods=['PUT'])
@lu_jwt_required
def update_dating_profile(account):
    """Create or update my dating profile."""
    from backend.domains.profile.models import DatingProfile
    data = request.get_json(silent=True) or {}

    dp = DatingProfile.query.filter_by(account_id=account.id).first()
    if not dp:
        dp = DatingProfile(id=str(uuid.uuid4()), account_id=account.id)
        db.session.add(dp)

    if 'display_name' in data:
        dp.display_name = (data['display_name'] or '').strip()[:200] or None
    if 'bio' in data:
        dp.bio = (data['bio'] or '').strip()[:1000] or None
    if 'birth_year' in data:
        by = data['birth_year']
        if isinstance(by, int) and 1930 <= by <= 2007:
            dp.birth_year = by
    if 'gender' in data:
        g = _norm_gender(data['gender'])
        if g:
            dp.gender = g  # only ever male/female
    if 'looking_for_gender' in data:
        dp.looking_for_gender = (data['looking_for_gender'] or '').strip() or None
    if 'age_min' in data:
        v = data['age_min']
        dp.age_min = max(18, min(80, int(v))) if v is not None else 18
    if 'age_max' in data:
        v = data['age_max']
        dp.age_max = max(18, min(80, int(v))) if v is not None else 60
    if dp.age_min and dp.age_max and dp.age_min > dp.age_max:
        dp.age_max = dp.age_min
    if 'intent' in data:
        valid_intents = ('open', 'relationship', 'casual', 'friends', 'marriage')
        if data['intent'] in valid_intents:
            dp.intent = data['intent']
    if 'discoverability' in data:
        valid_disc = ('discoverable', 'paused', 'incognito')
        if data['discoverability'] in valid_disc:
            dp.discoverability = data['discoverability']
    if 'lifestyle' in data:
        dp.lifestyle = data['lifestyle']
    if 'prompts' in data:
        dp.prompts = data['prompts']
    if 'max_distance_km' in data:
        v = data['max_distance_km']
        dp.max_distance_km = max(1, min(500, int(v))) if v is not None else None

    # Deeper attributes + preferences (P-API-03 / P-API-04) — pass-through.
    for field in ('relationship_goal', 'has_children', 'wants_children', 'smoking',
                  'drinking', 'religion', 'religiosity', 'tribe_ethnicity',
                  'education_level', 'love_languages', 'personality_type', 'diet',
                  'exercise', 'pets', 'voice_prompt_url', 'deal_breakers',
                  'sensitive_optin', 'photos', 'height_cm', 'sexual_orientation',
                  'marijuana', 'politics', 'body_type', 'zodiac', 'communication_style',
                  'languages_spoken', 'industry', 'region_id', 'district_id',
                  'country_code', 'preferences'):
        if field in data:
            setattr(dp, field, data[field])

    db.session.commit()
    return success_response('Dating profile updated.', dp.to_dict())


# ─── Preferences ("what you're looking for") — P-API-04 ──────────────────────

_DEFAULT_PREFERENCES = {
    'interested_in': [], 'age': {'min': 24, 'max': 35}, 'distance_km': 50,
    'height_cm': {'min': None, 'max': None}, 'relationship_goal': [],
    'wants_children': None, 'open_to_children': None, 'religion': [],
    'education_min': None, 'smoking': 'any', 'drinking': 'any', 'diet': None,
    'languages': [], 'tribe': [], 'politics': None, 'dealbreakers': [],
}


def _build_preferences(dp):
    """Merge stored preferences over defaults, seeded from the profile's
    canonical discovery filters (age range, gender, distance)."""
    from backend.shared.json_safe import as_obj
    prefs = dict(_DEFAULT_PREFERENCES)
    if dp:
        if dp.age_min or dp.age_max:
            prefs['age'] = {'min': dp.age_min or 18, 'max': dp.age_max or 60}
        if dp.looking_for_gender:
            prefs['interested_in'] = [dp.looking_for_gender]
        if dp.max_distance_km:
            prefs['distance_km'] = dp.max_distance_km
        prefs.update(as_obj(dp.preferences))
    return prefs


@sparks_bp.route('/preferences', methods=['GET'])
@lu_jwt_required
def get_preferences(account):
    """My 'looking for' preferences (every field, merged with defaults)."""
    from backend.domains.profile.models import DatingProfile
    dp = DatingProfile.query.filter_by(account_id=account.id).first()
    return success_response('Preferences loaded.', _build_preferences(dp))


@sparks_bp.route('/preferences', methods=['PUT'])
@lu_jwt_required
def update_preferences(account):
    """Update my 'looking for' preferences (updatable any time). Mirrors the
    canonical discovery filters (age/gender/distance) so the deck honours them."""
    from backend.domains.profile.models import DatingProfile
    from backend.shared.json_safe import as_obj
    data = request.get_json(silent=True) or {}

    dp = DatingProfile.query.filter_by(account_id=account.id).first()
    if not dp:
        dp = DatingProfile(id=str(uuid.uuid4()), account_id=account.id)
        db.session.add(dp)

    prefs = dict(_build_preferences(dp))
    for k, v in data.items():
        if k in _DEFAULT_PREFERENCES:
            prefs[k] = v
    dp.preferences = prefs

    # Mirror canonical discovery filters used by the deck.
    age = prefs.get('age') if isinstance(prefs.get('age'), dict) else {}
    if age.get('min') is not None:
        dp.age_min = max(18, min(80, int(age['min'])))
    if age.get('max') is not None:
        dp.age_max = max(18, min(80, int(age['max'])))
    if dp.age_min and dp.age_max and dp.age_min > dp.age_max:
        dp.age_max = dp.age_min
    if prefs.get('distance_km') is not None:
        dp.max_distance_km = max(1, min(500, int(prefs['distance_km'])))
    interested = prefs.get('interested_in') or []
    if len(interested) == 1:
        dp.looking_for_gender = interested[0]

    db.session.commit()
    return success_response('Preferences updated.', prefs)


@sparks_bp.route('/profile/step', methods=['PUT'])
@lu_jwt_required
def update_profile_step(account):
    """Save one wizard step's fields and return the updated dating-section
    completion so the wizard can advance its progress ring (P-API-05)."""
    from backend.domains.profile.models import DatingProfile
    from backend.domains.profile.service import calculate_completion
    data = request.get_json(silent=True) or {}
    fields = data.get('fields', data)  # accept {fields:{…}} or a flat body

    dp = DatingProfile.query.filter_by(account_id=account.id).first()
    if not dp:
        dp = DatingProfile(id=str(uuid.uuid4()), account_id=account.id)
        db.session.add(dp)
    saved = []
    for f in DatingProfile.ATTRIBUTE_FIELDS + ('bio', 'display_name', 'prompts',
                                               'photos', 'lifestyle', 'preferences'):
        if f in fields:
            if f == 'gender':
                g = _norm_gender(fields[f])
                if not g:
                    continue  # never persist a non male/female gender
                setattr(dp, f, g)
            else:
                setattr(dp, f, fields[f])
            saved.append(f)
    db.session.commit()

    comp = calculate_completion(account, None, [], [], 0, dating_profile=dp)
    dating = (comp.get('sections') or {}).get('dating', {})
    return success_response('Step saved.', {
        'saved': saved,
        'dating_completion_pct': dating.get('pct', 0),
        'dating_complete': dating.get('complete', False),
    })


@sparks_bp.route('/compatibility/<account_id>', methods=['GET'])
@sparks_mode_required
def compatibility(account, account_id):
    """Bidirectional preference compatibility between me and another member (P-API-06).
    Returns i_match_them / they_match_me / mutual_pct / breakdowns / dealbreaker."""
    from backend.domains.profile.models import DatingProfile
    from backend.domains.recommend.preference_match import compatibility as compute
    if account_id == account.id:
        return error_response('Cannot compare with yourself.')
    my_dp = DatingProfile.query.filter_by(account_id=account.id).first()
    their_dp = DatingProfile.query.filter_by(account_id=account_id).first()
    if not their_dp:
        return error_response('That member does not have a dating profile.', status_code=404)
    result = compute(my_dp, _build_preferences(my_dp),
                     their_dp, _build_preferences(their_dp))
    return success_response('Compatibility loaded.', result)


# ─── Incoming Likes ───────────────────────────────────────────────────────────

@sparks_bp.route('/likes', methods=['GET'])
@sparks_mode_required
def incoming_likes(account):
    """
    People who have sparked_up or standout on me, but I haven't acted on them yet.
    Free users see count + blurred profiles; premium sees full list.
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    # IDs I have already acted on
    my_acted = {s.target_id for s in Spark.query.filter_by(actor_id=account.id).all()}

    query = Spark.query.filter(
        Spark.target_id == account.id,
        Spark.action.in_(['spark_up', 'standout']),
    )
    if my_acted:
        query = query.filter(Spark.actor_id.notin_(my_acted))
    query = query.order_by(Spark.created_at.desc())

    items, total, page, last_page, per_page = paginate_query(query, page, per_page)

    unlocked = sub_service.can(account, 'can_view_likers')
    result = []
    for spark in items:
        d = spark.to_dict()
        if unlocked and spark.actor:
            actor_dict = spark.actor.to_dict()
            actor_dict['is_verified'] = bool((spark.actor.kyc_level or 0) >= 2)
            d['actor_account'] = actor_dict
        else:
            d['locked'] = True
        result.append(d)

    msg = f'{total} people liked you.' if unlocked else \
        f'{total} people liked you — upgrade to see who.'
    return paginated_response(result, total, page, per_page, msg)


# ─── Superlike daily count ────────────────────────────────────────────────────

@sparks_bp.route('/standout-count', methods=['GET'])
@lu_jwt_required
def standout_count(account):
    """How many standouts (super-likes) I have used today."""
    from datetime import date
    today_start = __import__('datetime').datetime.combine(date.today(), __import__('datetime').time.min)
    used = Spark.query.filter(
        Spark.actor_id == account.id,
        Spark.action == 'standout',
        Spark.created_at >= today_start,
    ).count()
    daily_limit = sub_service.get_limits(account).get('standouts_per_day', 1)
    remaining = -1 if daily_limit == -1 else max(0, daily_limit - used)
    return success_response('Standout count loaded.', {
        'used_today': used,
        'daily_limit': daily_limit,
        'remaining': remaining,
    })


# ─── Dating stats ─────────────────────────────────────────────────────────────

@sparks_bp.route('/stats', methods=['GET'])
@lu_jwt_required
def dating_stats(account):
    """Dashboard numbers: likes_received, new_matches, total_matches, sparks_sent."""
    from datetime import datetime, timedelta
    from backend.domains.sparks.models import Match

    # Likes received (unacted)
    my_acted = {s.target_id for s in Spark.query.filter_by(actor_id=account.id).all()}
    likes_q = Spark.query.filter(
        Spark.target_id == account.id,
        Spark.action.in_(['spark_up', 'standout']),
    )
    if my_acted:
        likes_q = likes_q.filter(Spark.actor_id.notin_(my_acted))
    likes_received = likes_q.count()

    # Total matches
    total_matches = Match.query.filter(
        db.or_(Match.account_a_id == account.id, Match.account_b_id == account.id),
        Match.state == 'active',
    ).count()

    # New matches (within last 7 days with no messages sent by me)
    week_ago = datetime.utcnow() - timedelta(days=7)
    new_matches = Match.query.filter(
        db.or_(Match.account_a_id == account.id, Match.account_b_id == account.id),
        Match.state == 'active',
        Match.created_at >= week_ago,
    ).count()

    # Sparks sent this week
    sparks_sent = Spark.query.filter(
        Spark.actor_id == account.id,
        Spark.action.in_(['spark_up', 'standout']),
        Spark.created_at >= week_ago,
    ).count()

    return success_response('Stats loaded.', {
        'likes_received': likes_received,
        'total_matches': total_matches,
        'new_matches': new_matches,
        'sparks_sent_week': sparks_sent,
    })


# ─── Engagement analytics (T-API: who's-viewing signals) ──────────────────────

@sparks_bp.route('/profile-viewers', methods=['GET'])
@sparks_mode_required
def profile_viewers(account):
    """Who viewed my profile — reuses the profile.view events already recorded
    by POST /analytics/event, no new tracking needed. Free users see the count
    only; premium (can_view_profile_viewers) sees the full identified list."""
    from backend.shared.events.models import BehavioralEvent
    from backend.domains.identity.models import Account

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    query = BehavioralEvent.query.filter(
        BehavioralEvent.verb == 'profile.view',
        BehavioralEvent.object_id == account.id,
        BehavioralEvent.account_id.isnot(None),
        BehavioralEvent.account_id != account.id,
    ).order_by(BehavioralEvent.created_at.desc())

    items, total, page, last_page, per_page = paginate_query(query, page, per_page)

    unlocked = sub_service.can(account, 'can_view_profile_viewers')
    result = []
    for ev in items:
        d = {'viewed_at': ev.created_at.isoformat() if ev.created_at else None}
        if unlocked:
            viewer = db.session.get(Account, ev.account_id)
            d['viewer'] = viewer.to_dict() if viewer else None
        else:
            d['locked'] = True
        result.append(d)

    msg = f'{total} people viewed your profile.' if unlocked else \
        f'{total} people viewed your profile — upgrade to see who.'
    return paginated_response(result, total, page, per_page, msg)


@sparks_bp.route('/analytics/event', methods=['POST'])
@lu_jwt_required
def analytics_event(account):
    """Record a lightweight engagement signal on another member's card.
    Body: { target_id, event }  event ∈ profile_view | photo_view.
    Append-only via the behavioral-event pipeline; never fails the request."""
    data = request.get_json(silent=True) or {}
    target_id = (data.get('target_id') or '').strip()
    event = (data.get('event') or '').strip().lower()
    if not target_id or event not in ('profile_view', 'photo_view'):
        return error_response('target_id and a valid event are required.')
    if target_id == account.id:
        return success_response('Ignored self-view.', {'recorded': False})

    from backend.shared.events.emit import emit
    verb = 'profile.view' if event == 'profile_view' else 'photo.view'
    emit(verb, account_id=account.id, object_type='account', object_id=target_id)

    # Real-time "someone viewed your profile" push — the one piece of this
    # notification system that reaches a genuinely offline user with fresh
    # data (a locally-scheduled reminder can only ever be as fresh as the
    # user's last app-open, since there's no backend scheduler to refresh
    # it). Same once-per-3h throttle as the spark_up/standout like-teaser
    # above, so a popular profile doesn't get a push per viewer.
    if verb == 'profile.view':
        try:
            from datetime import datetime, timedelta
            from backend.domains.identity.models import Account
            from backend.domains.notifications.models import Notification
            from backend.domains.notifications.service import create_notification
            recent_cutoff = datetime.utcnow() - timedelta(hours=3)
            recent = Notification.query.filter(
                Notification.account_id == target_id,
                Notification.type == 'profile.view',
                Notification.created_at > recent_cutoff,
            ).first()
            if not recent:
                target = db.session.get(Account, target_id)
                if target and sub_service.can(target, 'can_view_profile_viewers'):
                    create_notification(
                        account_id=target_id,
                        notif_type='profile.view',
                        title=f'{account.display_name} viewed your profile 👀',
                        body='Say hi before they move on.',
                        action_url='/sparks/profile-viewers',
                    )
                elif target:
                    # Free tier: same soft tease the in-app locked-viewer list
                    # already shows, just reaching people who aren't in the
                    # app right now — not a new paywall pattern, the existing
                    # one with a push in front of it.
                    create_notification(
                        account_id=target_id,
                        notif_type='profile.view',
                        title='Someone viewed your profile 👀',
                        body='Upgrade to see who.',
                        action_url='/sparks/profile-viewers',
                    )
        except Exception:
            pass

    return success_response('Recorded.', {'recorded': True})


@sparks_bp.route('/analytics/me', methods=['GET'])
@lu_jwt_required
def my_analytics(account):
    """My dating analytics: how others engaged with me + my own activity.
    Aggregated from sparks + behavioral events (last 30 days + all-time)."""
    from datetime import datetime, timedelta
    from backend.shared.events.models import BehavioralEvent

    since = datetime.utcnow() - timedelta(days=30)

    def _ev_count(verb, as_target, recent=False):
        q = BehavioralEvent.query.filter(BehavioralEvent.verb == verb)
        q = q.filter(BehavioralEvent.object_id == account.id) if as_target \
            else q.filter(BehavioralEvent.account_id == account.id)
        if recent:
            q = q.filter(BehavioralEvent.created_at >= since)
        return q.count()

    def _spark_count(action, as_target, recent=False):
        col = Spark.target_id if as_target else Spark.actor_id
        q = Spark.query.filter(col == account.id, Spark.action == action)
        if recent:
            q = q.filter(Spark.created_at >= since)
        return q.count()

    received = {
        'profile_views': _ev_count('profile.view', True),
        'profile_views_30d': _ev_count('profile.view', True, recent=True),
        'photo_views_30d': _ev_count('photo.view', True, recent=True),
        'likes': _spark_count('spark_up', True) + _spark_count('standout', True),
        'standouts': _spark_count('standout', True),
        'passes': _spark_count('pass', True),
    }
    given = {
        'likes': _spark_count('spark_up', False) + _spark_count('standout', False),
        'passes': _spark_count('pass', False),
        'profiles_viewed_30d': _ev_count('profile.view', False, recent=True),
    }
    return success_response('Analytics loaded.', {
        'received': received,
        'given': given,
    })


# ─── Dating profile photos ────────────────────────────────────────────────────

def _sync_avatar_from_dating_photos(account, photos):
    """Account.avatar is the single avatar shown everywhere outside the
    dating swipe deck — posts, chat, presence, the profile viewer's header —
    but these dating-photo routes only ever wrote to DatingProfile.photos.
    An account that only ever added dating photos (the norm for a
    dating-only app build, with no separate professional-avatar upload in
    reach) ended up with no avatar anywhere else and showed as bare
    initials everywhere. Mirror the first dating photo into Account.avatar,
    but never clobber an avatar the user explicitly set via the separate
    professional photo upload (distinguishable by its own storage folder)."""
    current = account.avatar or ''
    if current and '/dating_photos/' not in current:
        return
    account.avatar = photos[0]['url'] if photos else None


@sparks_bp.route('/profile/photos', methods=['POST'])
@lu_jwt_required
def add_dating_photo(account):
    """Append a photo URL to my dating profile photos list (max MAX_DATING_PHOTOS)."""
    from backend.domains.profile.models import DatingProfile
    data = request.get_json(silent=True) or {}
    url = (data.get('url') or '').strip()
    caption = (data.get('caption') or '').strip()[:200] or None

    if not url:
        return error_response('Photo URL is required.')
    if not (url.startswith('http://') or url.startswith('https://')):
        return error_response('Invalid URL.')

    dp = DatingProfile.query.filter_by(account_id=account.id).first()
    if not dp:
        dp = DatingProfile(id=str(uuid.uuid4()), account_id=account.id)
        db.session.add(dp)

    photos = list(dp.photos or [])
    if len(photos) >= MAX_DATING_PHOTOS:
        return error_response(f'Maximum {MAX_DATING_PHOTOS} photos allowed. Delete one first.')

    photos.append({'url': url, 'caption': caption})
    dp.photos = photos
    _sync_avatar_from_dating_photos(account, photos)
    db.session.commit()
    return success_response('Photo added.', {'photos': dp.photos})


@sparks_bp.route('/profile/photos/upload', methods=['POST'])
@lu_jwt_required
def upload_dating_photo(account):
    """Upload a photo file straight from the device onto my dating profile
    photos list (max MAX_DATING_PHOTOS). Same storage path as the professional avatar/cover
    upload, just appended to DatingProfile.photos instead of Account."""
    from backend.domains.profile.models import DatingProfile
    from backend.shared.storage.r2 import save_upload

    file = request.files.get('photo')
    if not file:
        return error_response('No photo file provided.')

    dp = DatingProfile.query.filter_by(account_id=account.id).first()
    if not dp:
        dp = DatingProfile(id=str(uuid.uuid4()), account_id=account.id)
        db.session.add(dp)

    photos = list(dp.photos or [])
    if len(photos) >= MAX_DATING_PHOTOS:
        return error_response(f'Maximum {MAX_DATING_PHOTOS} photos allowed. Delete one first.')

    url = save_upload(file, folder='dating_photos')
    if not url:
        return error_response('Failed to upload photo. Please use JPG, PNG, or WebP.')

    photos.append({'url': url, 'caption': None})
    dp.photos = photos
    _sync_avatar_from_dating_photos(account, photos)
    db.session.commit()
    return success_response('Photo added.', {'photos': dp.photos})


@sparks_bp.route('/profile/photos/<int:photo_index>', methods=['DELETE'])
@lu_jwt_required
def delete_dating_photo(account, photo_index):
    """Remove a photo by its index (0-based) from my dating profile."""
    from backend.domains.profile.models import DatingProfile

    dp = DatingProfile.query.filter_by(account_id=account.id).first()
    if not dp:
        return error_response('No dating profile found.')

    photos = list(dp.photos or [])
    if photo_index < 0 or photo_index >= len(photos):
        return error_response('Invalid photo index.')

    photos.pop(photo_index)
    dp.photos = photos
    _sync_avatar_from_dating_photos(account, photos)
    db.session.commit()
    return success_response('Photo removed.', {'photos': dp.photos})


@sparks_bp.route('/profile/photos/reorder', methods=['PUT'])
@lu_jwt_required
def reorder_dating_photos(account):
    """Reorder photos by supplying new index order: {order: [2, 0, 1]}."""
    from backend.domains.profile.models import DatingProfile
    data = request.get_json(silent=True) or {}
    order = data.get('order')

    if not isinstance(order, list):
        return error_response('order must be a list of indices.')

    dp = DatingProfile.query.filter_by(account_id=account.id).first()
    if not dp:
        return error_response('No dating profile found.')

    photos = list(dp.photos or [])
    if sorted(order) != list(range(len(photos))):
        return error_response('Invalid order — must contain each index exactly once.')

    dp.photos = [photos[i] for i in order]
    _sync_avatar_from_dating_photos(account, dp.photos)
    db.session.commit()
    return success_response('Photos reordered.', {'photos': dp.photos})
