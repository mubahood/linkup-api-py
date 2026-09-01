"""
Subscription entitlement service.

No scheduler exists in this codebase (no Celery/APScheduler) — expiry is a
lazy, self-healing check: every call to get_active_plan() first checks
whether the account's subscription_expires_at has passed and, if so, flips
the account back to the free plan and marks the ledger row expired before
returning. Nothing needs to run on a timer.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta
from backend.models import db
from backend.domains.subscriptions.models import SubscriptionPlan, Subscription

_FREE_CODE = 'free'


def _get_free_plan(app_id: str) -> SubscriptionPlan | None:
    return SubscriptionPlan.query.filter_by(app_id=app_id, code=_FREE_CODE, active=1).first()


def _downgrade_to_free(account) -> None:
    """Expire the account's current subscription and reset denormalized fields."""
    if account.subscription_plan_id:
        sub = Subscription.query.filter_by(
            account_id=account.id, plan_id=account.subscription_plan_id, status='active',
        ).order_by(Subscription.created_at.desc()).first()
        if sub:
            sub.status = 'expired'
    account.subscription_plan_id = None
    account.subscription_expires_at = None
    account.is_premium = 0
    db.session.commit()


def get_active_plan(account) -> SubscriptionPlan:
    """Return the account's currently-entitled plan, expiring it first if it lapsed."""
    if account.subscription_plan_id and account.subscription_expires_at:
        if account.subscription_expires_at < datetime.utcnow():
            _downgrade_to_free(account)
        else:
            plan = db.session.get(SubscriptionPlan, account.subscription_plan_id)
            if plan and plan.active:
                return plan
    free_plan = _get_free_plan(account.app_id)
    if free_plan:
        return free_plan
    # Should never happen post-migration seed, but never leave a caller with None.
    return SubscriptionPlan(app_id=account.app_id, code=_FREE_CODE, name='Free',
                            price_ugx=0, duration_days=0, limits={})


def get_limits(account) -> dict:
    plan = get_active_plan(account)
    return plan.limits if isinstance(plan.limits, dict) else {}


def touch_streak(account) -> int:
    """Record a day of genuine engagement (called from check_and_consume, so
    it fires on real swipe/chat activity, not just app-open). Idempotent per
    calendar day. Returns the current streak length in days."""
    now = datetime.utcnow()
    last = account.streak_updated_at
    if last is None:
        account.streak_days = 1
    elif last.date() == now.date():
        return account.streak_days or 1  # already touched today
    elif (now.date() - last.date()).days == 1:
        account.streak_days = (account.streak_days or 0) + 1
    else:
        account.streak_days = 1  # streak broken
    account.streak_updated_at = now
    db.session.commit()
    return account.streak_days


def _swipe_streak_bonus(account) -> int:
    """+10 bonus swipes at a 7-day streak, +5 at 3 days — a tiered reward,
    not additive, so it stays a clean, explainable number in the UI."""
    streak = account.streak_days or 0
    if streak >= 7:
        return 10
    if streak >= 3:
        return 5
    return 0


def grant_first_match_bonus(account) -> None:
    """Call when an account's first-ever match is created."""
    if not account.first_match_bonus_available:
        account.first_match_bonus_available = 1
        db.session.commit()


def check_and_consume(account, key: str, counter_fn) -> dict:
    """Generic quota check for a per-day limit.

    counter_fn: zero-arg callable returning today's usage count (since UTC
    midnight) for the metric being gated — e.g. a Spark/Message row count.

    Returns {allowed, used, limit, remaining, nudge?}. -1 limit = unlimited.
    Touches the engagement streak as a side effect (this function is only
    called on real swipe/standout/chat activity).
    """
    touch_streak(account)

    limits = get_limits(account)
    limit = limits.get(key, 0)
    if limit == -1:
        return {'allowed': True, 'used': 0, 'limit': -1, 'remaining': -1}

    streak_bonus = _swipe_streak_bonus(account) if key == 'swipes_per_day' else 0
    used = counter_fn()
    limit = int(limit) + streak_bonus
    bonus = streak_bonus

    # The first-match bonus only ever gets spent if it's actually needed to
    # cross the wall this call — so a bonus that arrives while the account
    # still has ordinary quota left stays banked for whenever it's needed,
    # instead of being silently burned the moment it's granted.
    if key == 'standouts_per_day' and used >= limit and account.first_match_bonus_available:
        limit += 1
        bonus += 1
        account.first_match_bonus_available = 0
        db.session.commit()

    remaining = max(0, limit - used)
    result = {'allowed': used < limit, 'used': used, 'limit': limit, 'remaining': remaining}
    if bonus:
        result['bonus'] = bonus
    if result['allowed'] and remaining <= 1:
        result['nudge'] = f'{remaining} left today — upgrade for unlimited.'
    if not result['allowed']:
        # UTC — the client converts to the device's local time before display,
        # so a Uganda-based user actually sees this in EAT without the server
        # needing to know or hardcode that offset.
        result['reset_at'] = (today_start() + timedelta(days=1)).isoformat()
    return result


def today_start() -> datetime:
    now = datetime.utcnow()
    return datetime(now.year, now.month, now.day)


def can(account, flag_key: str) -> bool:
    """Boolean entitlement check, e.g. can(account, 'can_view_likers')."""
    return bool(get_limits(account).get(flag_key, False))


def activate_subscription(sub: Subscription) -> dict:
    """Idempotently activate a verified subscription purchase (mirrors
    wallet/routes.py:_complete_topup). Additive renewal — stacking a purchase
    on an unexpired plan extends from the current expiry, rewarding renewal
    rather than resetting it.

    Both the redirect-verify route and the Flutterwave webhook call this for
    the same sub, often within moments of each other. The caller's own
    `sub.status == 'active'` read is unlocked, so re-fetch and lock both the
    subscription and account rows here, and re-check status only after the
    lock is held — otherwise two concurrent activations for one payment both
    apply the additive-renewal math, stacking duplicate duration for a
    single purchase."""
    from backend.domains.identity.models import Account

    locked_sub = Subscription.query.filter_by(id=sub.id).with_for_update().first()
    if not locked_sub or locked_sub.status == 'active':
        return {'already': True}

    account = Account.query.filter_by(id=locked_sub.account_id).with_for_update().first()
    plan = db.session.get(SubscriptionPlan, locked_sub.plan_id)

    now = datetime.utcnow()
    base = account.subscription_expires_at if (
        account.subscription_plan_id == locked_sub.plan_id
        and account.subscription_expires_at
        and account.subscription_expires_at > now
    ) else now
    expires_at = base + timedelta(days=plan.duration_days)

    locked_sub.status = 'active'
    locked_sub.starts_at = now
    locked_sub.expires_at = expires_at

    account.subscription_plan_id = plan.id
    account.subscription_expires_at = expires_at
    account.is_premium = 0 if plan.is_free else 1

    db.session.commit()
    return {
        'plan': plan.to_dict(),
        'expires_at': expires_at.isoformat(),
    }


def reconcile_stale_pending(account) -> None:
    """Lazy self-healing for a purchase whose redirect-verify never fired and
    whose webhook (if the Flutterwave dashboard webhook was never actually
    configured — an easy step to miss, and a real failure mode other
    Flutterwave integrations on this stack have hit in production) also
    never landed: a pending Subscription can otherwise sit unconfirmed
    forever even though the customer's money went through. Same lazy-check
    convention as get_active_plan()'s expiry check — no scheduler exists in
    this codebase, so re-verify opportunistically whenever the account
    naturally touches a subscription endpoint, rather than adding a cron
    job for what should be a rare fallback path."""
    stale_cutoff = datetime.utcnow() - timedelta(minutes=3)
    pending = Subscription.query.filter(
        Subscription.account_id == account.id,
        Subscription.status == 'pending',
        Subscription.created_at <= stale_cutoff,
    ).order_by(Subscription.created_at.desc()).first()
    if not pending:
        return
    try:
        from backend.services.flutterwave_service import FlutterwaveService
        flw = FlutterwaveService()
        resp = flw.verify_by_tx_ref(pending.tx_ref)
        if (flw.is_payment_successful(resp, float(pending.amount_paid_ugx), 'UGX')
                and resp.get('data', {}).get('tx_ref') == pending.tx_ref):
            pending.flw_tx_id = str(resp.get('data', {}).get('id', ''))
            activate_subscription(pending)
    except Exception:
        pass  # best-effort — the next natural touch point retries


def create_pending_subscription(account, plan: SubscriptionPlan) -> Subscription:
    sub = Subscription(
        id=str(uuid.uuid4()), account_id=account.id, plan_id=plan.id,
        status='pending', amount_paid_ugx=plan.effective_price_ugx,
        tx_ref=f'LU-SUB-{uuid.uuid4().hex[:10].upper()}',
        extra_data={'kind': 'subscription', 'plan_code': plan.code},
    )
    db.session.add(sub)
    db.session.commit()
    return sub
