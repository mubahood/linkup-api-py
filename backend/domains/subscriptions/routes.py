"""
Subscriptions routes: /v1/subscriptions/*

Purchase flow mirrors the wallet top-up flow exactly: create a pending
ledger row -> Flutterwave hosted payment link -> verify (redirect or
webhook) -> idempotent activation.
"""
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, request, current_app
from backend.models import db
from backend.domains.subscriptions.models import SubscriptionPlan, Subscription
from backend.domains.subscriptions import service as sub_service
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.idempotency import idempotent
from backend.shared.utils.response import success_response, error_response

subscriptions_bp = Blueprint('v1_subscriptions', __name__, url_prefix='/v1/subscriptions')


def _cfg(key, default):
    return current_app.config.get(key, default)


@subscriptions_bp.route('/plans', methods=['GET'])
@lu_jwt_required
def list_plans(account):
    """Active plans for the caller's app, cheapest first, plus the free plan's
    limits alongside each so the client can render a full comparison table in
    one call."""
    sub_service.reconcile_stale_pending(account)
    plans = SubscriptionPlan.query.filter_by(
        app_id=account.app_id, active=1,
    ).order_by(SubscriptionPlan.sort_order.asc()).all()
    free = next((p for p in plans if p.is_free), None)
    active_plan = sub_service.get_active_plan(account)
    return success_response('Plans loaded.', {
        'plans': [p.to_dict() for p in plans],
        'free_limits': free.limits if free else {},
        'current_plan_id': active_plan.id,
        'current_expires_at':
            account.subscription_expires_at.isoformat() if account.subscription_expires_at else None,
    })


@subscriptions_bp.route('/purchase', methods=['POST'])
@lu_jwt_required
@idempotent
def purchase(account):
    """Body: { plan_id, payment_method? }. payment_method is 'mobilemoney' or
    'card' — omit it to fall back to Flutterwave's own method-picker page.
    Returns a Flutterwave hosted-payment link; the plan activates only after
    the payment is verified (webhook or redirect-verify)."""
    from backend.services.flutterwave_service import FlutterwaveService

    data = request.get_json(silent=True) or {}
    plan_id = (data.get('plan_id') or '').strip()
    payment_method = (data.get('payment_method') or '').strip().lower()
    plan = db.session.get(SubscriptionPlan, plan_id)
    if not plan or plan.app_id != account.app_id or not plan.active:
        return error_response('Plan not found.', status_code=404)
    if plan.is_free:
        return error_response('The free plan does not require a purchase.')
    if payment_method and payment_method not in FlutterwaveService.PAYMENT_METHODS:
        return error_response('Choose either mobile money or card.')
    if payment_method == 'mobilemoney' and not (account.phone or '').strip():
        return error_response(
            'Add your phone number first so we know where to send the mobile '
            'money request.', status_code=422, data={'reason': 'phone_required'})

    sub = sub_service.create_pending_subscription(account, plan)

    try:
        flw = FlutterwaveService()
        redirect_url = (_cfg('APP_URL', 'http://localhost:5001')
                        + f'/v1/subscriptions/{sub.tx_ref}/verify')
        result = flw.initialize_payment(
            amount=float(sub.amount_paid_ugx), tx_ref=sub.tx_ref,
            customer_name=account.display_name or account.handle,
            customer_email=account.email or f'{account.handle}@linkup.app',
            customer_phone=account.phone or '',
            redirect_url=redirect_url, currency='UGX',
            payment_options=FlutterwaveService.PAYMENT_METHODS.get(payment_method),
            description=f'{plan.name} subscription',
            meta={'account_id': account.id, 'kind': 'subscription', 'plan_id': plan.id},
        )
        return success_response('Payment link created.', {
            'tx_ref': sub.tx_ref, 'payment_link': result['payment_link'],
            'plan': plan.to_dict(),
        })
    except Exception as e:
        # Don't leave a dead 'pending' row behind — nothing will ever verify
        # or webhook against a tx_ref that never reached Flutterwave.
        sub.status = 'cancelled'
        db.session.commit()
        # The real cause (missing key, network error, FLW-side rejection)
        # goes to the server log only — a user should never see raw config/
        # infra detail in a payment error. tx_ref is safe to surface: it's
        # just a reference number support can look up, not a secret.
        current_app.logger.error(f'[subscriptions.purchase] {sub.tx_ref}: {e}')
        return error_response(
            f'Payments are temporarily unavailable. Reference {sub.tx_ref} — '
            'please try again shortly.', status_code=502)


@subscriptions_bp.route('/<tx_ref>/verify', methods=['GET', 'POST'])
@lu_jwt_required
@idempotent
def verify(account, tx_ref):
    sub = Subscription.query.filter_by(tx_ref=tx_ref, account_id=account.id).first()
    if not sub:
        return error_response('Subscription purchase not found.', status_code=404)
    if sub.status == 'active':
        return success_response('Already active.', {'plan': sub.plan.to_dict()})

    flw_tx_id = (request.args.get('transaction_id')
                 or (request.get_json(silent=True) or {}).get('transaction_id', ''))
    verified = False
    if flw_tx_id and flw_tx_id != 'DEV_BYPASS':
        try:
            from backend.services.flutterwave_service import FlutterwaveService
            flw = FlutterwaveService()
            resp = flw.verify_by_id(flw_tx_id)
            if (flw.is_payment_successful(resp, float(sub.amount_paid_ugx), 'UGX')
                    and resp.get('data', {}).get('tx_ref') == tx_ref):
                verified = True
                sub.flw_tx_id = str(flw_tx_id)
        except Exception:
            verified = False

    if not verified and flw_tx_id == 'DEV_BYPASS' and current_app.config.get('DEBUG'):
        verified = True

    if not verified:
        return error_response('Payment not verified yet.', status_code=422)

    result = sub_service.activate_subscription(sub)
    return success_response('Subscription activated.', result)


@subscriptions_bp.route('/webhook/flutterwave', methods=['POST'])
def webhook():
    """Public webhook — fallback completion path if the redirect-verify never
    fires (matches wallet/routes.py:flutterwave_webhook)."""
    from backend.services.flutterwave_service import FlutterwaveService
    flw = FlutterwaveService()
    received = request.headers.get('verif-hash') or request.headers.get('verifi-hash')
    if not flw.verify_webhook_hash(received):
        return error_response('Invalid signature.', status_code=401)

    payload = request.get_json(silent=True) or {}
    data = payload.get('data') or {}
    tx_ref = data.get('tx_ref') or ''
    if not tx_ref.startswith('LU-SUB-'):
        return success_response('Ignored.', {'handled': False})

    status = (data.get('status') or '').lower()
    sub = Subscription.query.filter_by(tx_ref=tx_ref).first()
    if sub and sub.status == 'pending' and status == 'successful':
        try:
            resp = flw.verify_by_id(str(data.get('id')))
            if flw.is_payment_successful(resp, float(sub.amount_paid_ugx), 'UGX'):
                sub.flw_tx_id = str(data.get('id'))
                sub_service.activate_subscription(sub)
        except Exception:
            pass
    return success_response('Handled.', {'handled': True})


@subscriptions_bp.route('/me', methods=['GET'])
@lu_jwt_required
def me(account):
    """Current plan + expiry + today's usage snapshot — powers the mobile
    'my plan' screen and near-limit nudges."""
    from backend.domains.sparks.models import Spark
    from backend.domains.chat.models import Message

    sub_service.reconcile_stale_pending(account)
    plan = sub_service.get_active_plan(account)
    today_start = sub_service.today_start()

    swipes_used = Spark.query.filter(
        Spark.actor_id == account.id,
        Spark.action.in_(['spark_up', 'pass']),
        Spark.created_at >= today_start,
    ).count()
    standouts_used = Spark.query.filter(
        Spark.actor_id == account.id, Spark.action == 'standout',
        Spark.created_at >= today_start,
    ).count()
    chats_used = Message.query.filter(
        Message.sender_id == account.id, Message.created_at >= today_start,
    ).count()

    def _remaining(limit, used):
        return -1 if limit == -1 else max(0, int(limit) - used)

    limits = plan.limits if isinstance(plan.limits, dict) else {}
    return success_response('Subscription loaded.', {
        'plan': plan.to_dict(),
        'expires_at':
            account.subscription_expires_at.isoformat() if account.subscription_expires_at else None,
        'streak_days': account.streak_days or 0,
        'first_match_bonus_available': bool(account.first_match_bonus_available),
        # All three counters below share this same UTC-midnight boundary, so
        # one reset time covers them — the client converts to local time.
        'reset_at': (today_start + timedelta(days=1)).isoformat(),
        'usage_today': {
            'swipes': {'used': swipes_used, 'limit': limits.get('swipes_per_day', 0),
                       'remaining': _remaining(limits.get('swipes_per_day', 0), swipes_used)},
            'standouts': {'used': standouts_used, 'limit': limits.get('standouts_per_day', 0),
                          'remaining': _remaining(limits.get('standouts_per_day', 0), standouts_used)},
            'chats': {'used': chats_used, 'limit': limits.get('chats_per_day', 0),
                      'remaining': _remaining(limits.get('chats_per_day', 0), chats_used)},
        },
    })
