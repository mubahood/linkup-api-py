"""
Sparks service: deck generation, match creation.
"""
import uuid
from sqlalchemy import or_
from backend.models import db
from backend.domains.sparks.models import Spark, Match
from backend.domains.identity.models import Account
from backend.domains.profile.models import DatingProfile


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return great-circle distance in km between two GPS points."""
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _opposite_gender(g: str | None):
    """Opposite-gender candidate tokens for deck recycling. Handles both
    vocabularies (male/man, female/woman) so it works regardless of which the
    profile was saved with. Returns a tuple of tokens, or None for
    non-binary/other/unset (then no gender filter is applied)."""
    if not g:
        return None
    g = g.lower().strip()
    if g in ('male', 'man', 'm'):
        return ('female', 'woman')
    if g in ('female', 'woman', 'w', 'f'):
        return ('male', 'man')
    return None


def _gender_token_set(values):
    """Expand requested gender filters across both vocabularies (male/man,
    female/woman) so the filter matches regardless of how a profile was saved."""
    if not values:
        return None
    out = set()
    for v in values:
        v = (v or '').lower().strip()
        if not v:
            continue
        out.add(v)
        if v in ('male', 'man'):
            out |= {'male', 'man'}
        elif v in ('female', 'woman'):
            out |= {'female', 'woman'}
    return out or None


def get_deck(account_id: str, limit: int = 20, allow_passed: bool = False,
             max_distance_km: float = None, filters: dict = None) -> list:
    """
    Generate a discovery deck ordered by Interest Graph compatibility.

    Excludes:
    - Already acted-on profiles
    - Blocked accounts (both directions)
    - Heavily-reported accounts
    - Self
    - Paused / incognito profiles (discoverability)

    Filters:
    - Actor's age preference vs candidate's birth_year
    - Candidate's age preference vs actor's birth_year
    - Gender preference (soft match — never hard-reject if no preference set)
    """
    import json
    from datetime import date
    from backend.domains.safety.models import Block, Report
    from backend.domains.recommend.service import rank_candidates  # unified seam (T-API-029)

    # Determine exclusion set:
    # allow_passed=True → only exclude spark_up/standout (matches), not pass actions
    if allow_passed:
        # Only exclude positive actions — allow re-discovery of passed profiles
        acted_ids = {
            s.target_id for s in Spark.query.filter_by(actor_id=account_id).filter(
                Spark.action.in_(['spark_up', 'standout'])
            ).all()
        }
    else:
        acted_ids = {s.target_id for s in Spark.query.filter_by(actor_id=account_id).all()}

    blocked_ids = (
        {b.blocked_id for b in Block.query.filter_by(blocker_id=account_id).all()} |
        {b.blocker_id for b in Block.query.filter_by(blocked_id=account_id).all()}
    )
    # Heavily-reported accounts (reported ≥3 times) get excluded from deck
    from sqlalchemy import func
    reported_counts = (
        db.session.query(Report.target_account_id, func.count(Report.id).label('cnt'))
        .group_by(Report.target_account_id)
        .having(func.count(Report.id) >= 3)
        .all()
    )
    reported_ids = {row[0] for row in reported_counts}

    excluded = acted_ids | blocked_ids | reported_ids | {account_id}

    # Load the actor's own dating profile up front — needed to decide the
    # default gender (opposite sex) before we build the candidate query.
    actor_dating = DatingProfile.query.filter_by(account_id=account_id).first()
    actor_birth_year = actor_dating.birth_year if actor_dating else None
    actor_age = (date.today().year - actor_birth_year) if actor_birth_year else None
    actor_gender = actor_dating.gender if actor_dating else None
    actor_age_min = actor_dating.age_min if actor_dating else 18
    actor_age_max = actor_dating.age_max if actor_dating else 99
    actor_looking_for = actor_dating.looking_for_gender if actor_dating else None

    # ── Advanced filters (T-API: explicit discovery filters) ───────────────────
    fl = filters or {}
    f_genders = _gender_token_set(fl.get('genders'))
    f_country = fl.get('country_code')
    f_region = fl.get('region_id')
    f_intents = set(fl.get('intents') or [])
    f_drink = set(fl.get('drinking') or [])
    f_smoke = set(fl.get('smoking') or [])
    f_has_photos = bool(fl.get('has_photos'))
    f_verified = bool(fl.get('verified_only'))
    f_age_min = fl.get('age_min')
    f_age_max = fl.get('age_max')

    # CORE RULE: with no explicit gender filter, default to the OPPOSITE sex
    # (man → women, woman → men). Falls back to no filter only when the actor's
    # gender is unknown/non-binary.
    opp = _opposite_gender(actor_gender)
    eff_genders = f_genders if f_genders else (set(opp) if opp else None)

    def _apply_query_filters(q):
        if eff_genders:
            q = q.filter(func.lower(DatingProfile.gender).in_(eff_genders))
        if f_country:
            q = q.filter(DatingProfile.country_code == f_country)
        if f_region:
            q = q.filter(DatingProfile.region_id == f_region)
        return q

    def _passes_filters(acc, dp):
        if f_intents and (dp.intent or '').lower() not in f_intents:
            return False
        if f_drink and (dp.drinking or '').lower() not in f_drink:
            return False
        if f_smoke and (dp.smoking or '').lower() not in f_smoke:
            return False
        if f_has_photos and not ((dp.photos and len(dp.photos) >= 1) or bool(acc.avatar)):
            return False
        if f_verified and not ((getattr(acc, 'kyc_level', 0) or 0) > 0):
            return False
        # Explicit age range (applies in both the main pool and the recycle pass).
        if (f_age_min is not None or f_age_max is not None) and dp.birth_year:
            age = date.today().year - dp.birth_year
            if age < (f_age_min or 18) or age > (f_age_max or 99):
                return False
        return True

    # Fetch a wider pool (5× limit) to allow filtering + scoring
    pool_size = limit * 5
    query = db.session.query(Account, DatingProfile).join(
        DatingProfile, DatingProfile.account_id == Account.id
    ).filter(
        Account.id.notin_(excluded) if excluded else True,
        Account.account_status == 'active',
        Account.deleted_at.is_(None),
        DatingProfile.discoverability == 'discoverable',  # paused/incognito excluded
    )
    query = _apply_query_filters(query).limit(pool_size)
    rows = query.all()

    # Explicit age filter overrides the actor's saved preference when provided.
    eff_age_min = f_age_min if f_age_min is not None else actor_age_min
    eff_age_max = f_age_max if f_age_max is not None else actor_age_max

    current_year = date.today().year

    sparks_accounts = []
    dating_map: dict = {}

    for acc, dp in rows:
        # Check sparks mode enabled
        if not acc.modes.get('sparks', False):  # safe accessor (T-API-041)
            continue

        # Explicit advanced filters (intent / lifestyle / photos / verified).
        if not _passes_filters(acc, dp):
            continue

        # Age preference filter (soft — skip if no birth_year data)
        if dp.birth_year:
            candidate_age = current_year - dp.birth_year
            # Actor's (or the filter's) preferred age range.
            if candidate_age < eff_age_min or candidate_age > eff_age_max:
                continue
            # Candidate's preference: is actor within candidate's preferred range?
            if actor_age:
                cand_min = dp.age_min or 18
                cand_max = dp.age_max or 99
                if actor_age < cand_min or actor_age > cand_max:
                    continue

        # Candidate gender is already constrained by eff_genders (opposite sex
        # by default). Still respect the candidate's own preference — don't show
        # someone who isn't open to the actor's gender.
        if dp.looking_for_gender and actor_gender:
            if dp.looking_for_gender.lower() not in ('any', 'all', '') and \
               actor_gender.lower() != dp.looking_for_gender.lower():
                continue

        # Distance filter — only if BOTH parties have GPS and caller requested it
        if max_distance_km is not None:
            actor_acct = db.session.get(Account, account_id)
            if (actor_acct and actor_acct.last_lat is not None and actor_acct.last_lng is not None
                    and acc.last_lat is not None and acc.last_lng is not None):
                dist = _haversine_km(
                    float(actor_acct.last_lat), float(actor_acct.last_lng),
                    float(acc.last_lat), float(acc.last_lng),
                )
                if dist > max_distance_km:
                    continue

        sparks_accounts.append(acc)
        dating_map[acc.id] = dp

    # ── Guarantee a useful deck (min 15), closest matches first ────────────────
    # Strict filters can over-restrict (or the deck can be exhausted). If the
    # strict set is thin, top it up with the *closest* candidates — those that
    # satisfy the most requested filters — relaxing the soft filters but keeping
    # gender relevant. Repeats are allowed only as a last resort, so the deck
    # never dead-ends.
    MIN_DECK = 15
    target = max(limit, MIN_DECK)

    def _match_score(acc, dp):
        """How many requested filters this candidate satisfies (gender weighs
        most). Drives 'closest match first' ordering."""
        s = 0
        if f_genders:
            s += 5 if (dp.gender or '').lower() in f_genders else 0
        if f_intents:
            s += 2 if (dp.intent or '').lower() in f_intents else 0
        if f_drink:
            s += 1 if (dp.drinking or '').lower() in f_drink else 0
        if f_smoke:
            s += 1 if (dp.smoking or '').lower() in f_smoke else 0
        if f_has_photos:
            s += 1 if ((dp.photos and len(dp.photos) >= 1) or bool(acc.avatar)) else 0
        if f_verified:
            s += 1 if ((getattr(acc, 'kyc_level', 0) or 0) > 0) else 0
        if (f_age_min is not None or f_age_max is not None) and dp.birth_year:
            cage = date.today().year - dp.birth_year
            s += 2 if (f_age_min or 18) <= cage <= (f_age_max or 99) else 0
        return s

    if len(sparks_accounts) < target:
        have = {a.id for a in sparks_accounts}
        broad = db.session.query(Account, DatingProfile).join(
            DatingProfile, DatingProfile.account_id == Account.id
        ).filter(
            Account.account_status == 'active',
            Account.deleted_at.is_(None),
            DatingProfile.discoverability == 'discoverable',
        )
        safety = blocked_ids | reported_ids | {account_id}
        if safety:
            broad = broad.filter(Account.id.notin_(safety))
        # Gender (opposite sex by default, or explicit filter) is never relaxed.
        if eff_genders:
            broad = broad.filter(func.lower(DatingProfile.gender).in_(eff_genders))
        pool = [(a, d) for a, d in broad.limit(target * 10).all()
                if a.modes.get('sparks', False)]
        # Closest first; among equals, prefer not-yet-acted-on profiles.
        pool.sort(key=lambda x: (-_match_score(*x), x[0].id in acted_ids))
        for a, d in pool:
            if a.id in have:
                continue
            sparks_accounts.append(a)
            dating_map[a.id] = d
            have.add(a.id)
            if len(sparks_accounts) >= target:
                break

    if not sparks_accounts:
        return []

    # Rank by Interest Graph overlap (dating mode)
    candidate_ids = [acc.id for acc in sparks_accounts]
    ranked = rank_candidates(account_id, candidate_ids, mode='dating')

    # Build result in ranked order (up to limit)
    acc_map = {acc.id: acc for acc in sparks_accounts}

    # When filters are active, surface the closest matches first (most filters
    # satisfied), using the interest-graph rank only as a tiebreaker.
    any_filter = bool(f_genders or f_intents or f_drink or f_smoke
                      or f_has_photos or f_verified
                      or f_age_min is not None or f_age_max is not None)
    rank_score = dict(ranked)
    rank_pos = {cid: i for i, (cid, _) in enumerate(ranked)}
    ordered_ids = list(acc_map.keys())
    if any_filter:
        ordered_ids.sort(key=lambda cid: (
            -_match_score(acc_map[cid], dating_map[cid]),
            rank_pos.get(cid, 10 ** 9),
        ))
    else:
        ordered_ids.sort(key=lambda cid: rank_pos.get(cid, 10 ** 9))

    # Batch-fetch interest tags for all candidates
    candidate_ids_set = set(acc_map.keys())
    interest_map: dict = {}
    try:
        from backend.domains.interest.models import AccountInterest, Interest
        rows = db.session.query(AccountInterest, Interest).join(
            Interest, Interest.id == AccountInterest.interest_id
        ).filter(AccountInterest.account_id.in_(candidate_ids_set)).all()
        for ai, interest in rows:
            interest_map.setdefault(ai.account_id, []).append({
                'id': interest.id,
                'display_name_en': interest.display_name_en,
            })
    except Exception:
        pass

    # Actor's own interest ids — for the "why you're seeing this" reason (T-API-052)
    my_interest_ids: set = set()
    try:
        from backend.domains.interest.models import AccountInterest
        my_interest_ids = {
            ai.interest_id for ai in
            AccountInterest.query.filter_by(account_id=account_id).all()
        }
    except Exception:
        pass

    def _spark_why(pct, shared, dp):
        bits = []
        if shared >= 3:
            bits.append(f'{shared} shared interests')
        elif shared > 0:
            bits.append(f'{shared} shared interest{"s" if shared > 1 else ""}')
        if dp and dp.get('relationship_goal'):
            bits.append(f'both open to {dp["relationship_goal"].replace("_", " ")}')
        lead = 'Strong match' if pct >= 75 else ('Good match' if pct >= 50 else 'Worth a look')
        return f'{lead} · ' + ' · '.join(bits) if bits else lead

    # Sensitive fields that must never appear on swipe cards
    _STRIP = {'phone', 'email', 'email_verified', 'phone_verified',
              'kyc_level', 'modes_enabled', 'location_id', 'reputation_score',
              'cover_photo', 'is_online', 'last_seen_at', 'updated_at', 'created_at'}

    # Preference compatibility (P-API-07): load the viewer's prefs once.
    from backend.shared.json_safe import as_obj
    from backend.domains.recommend.preference_match import compatibility as _compat
    _my_prefs = as_obj(actor_dating.preferences) if actor_dating else {}

    result = []
    for cid in ordered_ids[:limit]:
        score = rank_score.get(cid, 0.0)
        acc = acc_map.get(cid)
        if not acc:
            continue
        card = {k: v for k, v in acc.to_dict().items() if k not in _STRIP}
        dating = dating_map.get(cid)
        dp_dict = dating.to_dict() if dating else None
        card['dating_profile'] = dp_dict
        # Bidirectional preference match for the card (P-API-07).
        if actor_dating and dating:
            _c = _compat(actor_dating, _my_prefs, dating, as_obj(dating.preferences))
            card['mutual_pct'] = _c['mutual_pct']
            card['preference_dealbreaker'] = _c['dealbreaker']
        # Build photo gallery: dating photos first, then avatar fallback
        photos = (dp_dict.get('photos') or []) if dp_dict else []
        if not photos and card.get('avatar'):
            photos = [{'url': card['avatar']}]
        card['photos'] = photos
        card['compatibility_score'] = round(score, 3)
        card['compatibility_pct'] = min(99, max(1, round(score * 100)))
        cand_ids = {t['id'] for t in interest_map.get(cid, [])}
        shared = len(my_interest_ids & cand_ids)
        card['shared_interest_count'] = shared
        card['why'] = _spark_why(card['compatibility_pct'], shared, dp_dict)
        card['interest_tags'] = interest_map.get(cid, [])
        result.append(card)
    return result


# Sensitive fields that must never appear on a discovery card.
_CARD_STRIP = {'phone', 'email', 'email_verified', 'phone_verified',
               'kyc_level', 'modes_enabled', 'location_id', 'reputation_score',
               'cover_photo', 'is_online', 'last_seen_at', 'updated_at', 'created_at'}


def search_people(account_id: str, direction: str = 'outgoing',
                  page: int = 1, per_page: int = 30) -> dict:
    """Ranked, *unlimited* people search by preference compatibility.

    direction='outgoing' → **People I'm searching for**: candidates ranked by how
        well they fit MY preferences (``i_match_them``).
    direction='incoming' → **People searching for me**: people ranked by how well
        I fit THEIR preferences (``they_match_me``).

    The match is "almost, not exact" by design — every eligible person is scored
    and the *most relevant float to the top*; no one is hard-excluded on a near
    miss. There is no artificial cap: the full pool is ranked and only sliced for
    delivery (page / per_page), so the mobile list can scroll indefinitely.
    """
    import math
    from datetime import date  # noqa: F401  (kept for parity/future use)
    from sqlalchemy import func
    from backend.domains.safety.models import Block, Report
    from backend.shared.json_safe import as_obj
    from backend.domains.recommend.preference_match import compatibility

    direction = 'incoming' if (direction or '').lower() == 'incoming' else 'outgoing'
    page = max(1, int(page or 1))
    per_page = max(1, min(int(per_page or 30), 60))

    actor_dating = DatingProfile.query.filter_by(account_id=account_id).first()
    actor_gender = actor_dating.gender if actor_dating else None
    my_prefs = as_obj(actor_dating.preferences) if actor_dating else {}

    # Safety exclusions: self + blocks (both directions) + heavily-reported.
    blocked_ids = (
        {b.blocked_id for b in Block.query.filter_by(blocker_id=account_id).all()} |
        {b.blocker_id for b in Block.query.filter_by(blocked_id=account_id).all()}
    )
    reported = (
        db.session.query(Report.target_account_id)
        .group_by(Report.target_account_id)
        .having(func.count(Report.id) >= 3).all()
    )
    excluded = blocked_ids | {r[0] for r in reported} | {account_id}

    # Dating pool = opposite sex by default (same CORE rule as the deck).
    opp = _opposite_gender(actor_gender)
    eff_genders = set(opp) if opp else None

    q = db.session.query(Account, DatingProfile).join(
        DatingProfile, DatingProfile.account_id == Account.id
    ).filter(
        Account.account_status == 'active',
        Account.deleted_at.is_(None),
        DatingProfile.discoverability == 'discoverable',
    )
    if excluded:
        q = q.filter(Account.id.notin_(excluded))
    if eff_genders:
        q = q.filter(func.lower(DatingProfile.gender).in_(eff_genders))

    scored = []
    for acc, dp in q.all():
        if not acc.modes.get('sparks', False):  # safe accessor
            continue
        comp = compatibility(actor_dating, my_prefs, dp, as_obj(dp.preferences))
        side = comp['they_match_me'] if direction == 'incoming' else comp['i_match_them']
        scored.append({
            'pct': side['pct'],
            'satisfied': side['satisfied'],
            'total': side['total'],
            'mutual': comp['mutual_pct'],
            'dealbreaker': comp['dealbreaker'],
            'acc': acc,
            'dp': dp,
        })

    # Most relevant first: match% → #criteria actually satisfied (so a real 5/5
    # outranks a vacuous 0/0 = 100%) → mutual% as final tiebreak.
    scored.sort(key=lambda e: (-e['pct'], -e['satisfied'], -e['mutual']))

    total = len(scored)
    start = (page - 1) * per_page
    page_rows = scored[start:start + per_page]

    # Interest tags for just this page.
    page_ids = [e['acc'].id for e in page_rows]
    interest_map: dict = {}
    if page_ids:
        try:
            from backend.domains.interest.models import AccountInterest, Interest
            rows = db.session.query(AccountInterest, Interest).join(
                Interest, Interest.id == AccountInterest.interest_id
            ).filter(AccountInterest.account_id.in_(page_ids)).all()
            for ai, interest in rows:
                interest_map.setdefault(ai.account_id, []).append({
                    'id': interest.id,
                    'display_name_en': interest.display_name_en,
                })
        except Exception:
            pass

    items = []
    for e in page_rows:
        acc, dp = e['acc'], e['dp']
        card = {k: v for k, v in acc.to_dict().items() if k not in _CARD_STRIP}
        dp_dict = dp.to_dict()
        card['dating_profile'] = dp_dict
        photos = (dp_dict.get('photos') or [])
        if not photos and card.get('avatar'):
            photos = [{'url': card['avatar']}]
        card['photos'] = photos
        # Headline percentage for this direction (most-relevant ordering).
        card['match_pct'] = e['pct']
        card['mutual_pct'] = e['mutual']
        card['preference_dealbreaker'] = e['dealbreaker']
        card['interest_tags'] = interest_map.get(acc.id, [])
        items.append(card)

    return {
        'direction': direction,
        'data': items,
        'current_page': page,
        'per_page': per_page,
        'total': total,
        'last_page': max(1, math.ceil(total / per_page)) if total else 1,
    }


def record_action(actor_id: str, target_id: str, action: str) -> tuple[Spark, Match | None]:
    """Record a spark action and check for a mutual match."""
    # Upsert the spark (on duplicate, update action)
    existing = Spark.query.filter_by(actor_id=actor_id, target_id=target_id).first()
    if existing:
        existing.action = action
        spark = existing
    else:
        spark = Spark(
            id=str(uuid.uuid4()),
            actor_id=actor_id,
            target_id=target_id,
            action=action,
        )
        db.session.add(spark)

    db.session.flush()

    match = None
    if action in ('spark_up', 'standout'):
        # Check if target has sparked back
        reverse = Spark.query.filter_by(
            actor_id=target_id, target_id=actor_id
        ).filter(Spark.action.in_(['spark_up', 'standout'])).first()

        if reverse:
            # Check no existing match
            existing_match = Match.query.filter(
                or_(
                    (Match.account_a_id == actor_id) & (Match.account_b_id == target_id),
                    (Match.account_a_id == target_id) & (Match.account_b_id == actor_id),
                )
            ).first()
            if not existing_match:
                match = Match(
                    id=str(uuid.uuid4()),
                    account_a_id=actor_id,
                    account_b_id=target_id,
                    spark_a_id=spark.id,
                    spark_b_id=reverse.id,
                )
                db.session.add(match)
                db.session.flush()
                # Auto-create a Sparks direct thread for the match
                _create_match_thread(match, actor_id, target_id)

    db.session.commit()
    return spark, match


def _create_match_thread(match: Match, account_a: str, account_b: str):
    """Create a Sparks-mode direct thread for a new match."""
    from datetime import datetime
    from backend.domains.chat.models import Thread, ThreadParticipant
    thread = Thread(
        id=str(uuid.uuid4()),
        type='spark',
        mode='dating',
        created_by=account_a,
        last_message_at=datetime.utcnow(),
    )
    db.session.add(thread)
    db.session.flush()
    for pid in [account_a, account_b]:
        db.session.add(ThreadParticipant(
            id=str(uuid.uuid4()),
            thread_id=thread.id,
            account_id=pid,
        ))
    match.thread_id = thread.id
