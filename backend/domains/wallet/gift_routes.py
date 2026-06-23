"""
Gifting routes: /v1/gifts/*

Coins (bought) → gifts → recipient REDEEMABLE cash (90%) → redeem → withdrawable.
"""
import uuid
from flask import Blueprint, request, current_app
from sqlalchemy import func
from backend.models import db
from backend.domains.wallet.models import (
    WalletAccount, WalletTransaction, GiftCatalog, Gift,
)
from backend.domains.identity.models import Account
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.idempotency import idempotent
from backend.shared.utils.response import success_response, error_response, paginated_response
from backend.shared.utils.pagination import paginate_query

gifts_bp = Blueprint('v1_gifts', __name__, url_prefix='/v1/gifts')


def _cfg(key, default):
    return current_app.config.get(key, default)


def _wallet(account_id, lock=False):
    q = WalletAccount.query.filter_by(account_id=account_id)
    if lock:
        q = q.with_for_update()
    w = q.first()
    if not w:
        w = WalletAccount(id=str(uuid.uuid4()), account_id=account_id,
                          balance=0.00, currency='UGX')
        db.session.add(w)
        db.session.commit()
        if lock:
            w = WalletAccount.query.filter_by(
                account_id=account_id).with_for_update().first()
    return w


def _ledger(wallet, account_id, *, type_, category, amount, description, extra=None):
    db.session.add(WalletTransaction(
        id=str(uuid.uuid4()), wallet_id=wallet.id, account_id=account_id,
        type=type_, category=category, amount=amount,
        balance_before=float(wallet.balance), balance_after=float(wallet.balance),
        description=description, status='completed', extra_data=extra,
    ))


@gifts_bp.route('/catalog', methods=['GET'])
@lu_jwt_required
def catalog(account):
    items = GiftCatalog.query.filter_by(active=1)\
        .order_by(GiftCatalog.sort_order.asc()).all()
    return success_response('Catalog loaded.', [g.to_dict() for g in items])


@gifts_bp.route('/summary', methods=['GET'])
@lu_jwt_required
def summary(account):
    w = _wallet(account.id)
    received = db.session.query(
        func.count(Gift.id), func.coalesce(func.sum(Gift.net_ugx), 0)
    ).filter(Gift.recipient_id == account.id).first()
    sent = db.session.query(func.count(Gift.id))\
        .filter(Gift.sender_id == account.id).scalar()
    return success_response('Summary loaded.', {
        'coins': int(w.coins or 0),
        'redeemable_ugx': float(w.redeemable or 0),
        'balance_ugx': float(w.balance or 0),
        'gifts_received': int(received[0] or 0),
        'gifts_received_value_ugx': float(received[1] or 0),
        'gifts_sent': int(sent or 0),
    })


@gifts_bp.route('/send', methods=['POST'])
@lu_jwt_required
@idempotent
def send_gift(account):
    """Body: { recipient_id, gift_code, context_type?, context_id?, message? }."""
    data = request.get_json(silent=True) or {}
    recipient_id = (data.get('recipient_id') or '').strip()
    gift_code = (data.get('gift_code') or '').strip()
    if not recipient_id or not gift_code:
        return error_response('recipient_id and gift_code are required.')
    if recipient_id == account.id:
        return error_response('You can’t gift yourself.')

    recipient = Account.query.filter_by(id=recipient_id).first()
    if not recipient or recipient.deleted_at is not None:
        return error_response('Recipient not found.', status_code=404)

    # Respect blocks (either direction).
    try:
        from backend.domains.safety.models import Block
        blocked = Block.query.filter(
            ((Block.blocker_id == account.id) & (Block.blocked_id == recipient_id)) |
            ((Block.blocker_id == recipient_id) & (Block.blocked_id == account.id))
        ).first()
        if blocked:
            return error_response('You can’t send a gift to this person.')
    except Exception:
        pass

    gift = GiftCatalog.query.filter_by(code=gift_code, active=1).first()
    if not gift:
        return error_response('Gift not available.', status_code=404)

    fee_pct = float(_cfg('GIFT_PLATFORM_FEE_PCT', 10))
    cash_value = float(gift.cash_value_ugx)
    fee = round(cash_value * fee_pct / 100.0, 2)
    net = round(cash_value - fee, 2)
    price = int(gift.price_coins)

    # Debit sender coins under lock.
    sw = _wallet(account.id, lock=True)
    if int(sw.coins or 0) < price:
        db.session.rollback()
        return error_response('Not enough coins. Top up to send this gift.',
                              data={'needed_coins': price, 'coins': int(sw.coins or 0)})
    sw.coins = int(sw.coins or 0) - price

    g = Gift(
        id=str(uuid.uuid4()), sender_id=account.id, recipient_id=recipient_id,
        gift_code=gift.code, gift_name=gift.name, coins_spent=price,
        cash_value_ugx=cash_value, platform_fee_ugx=fee, net_ugx=net,
        context_type=(data.get('context_type') or None),
        context_id=(data.get('context_id') or None),
        message=(data.get('message') or '')[:300] or None,
    )
    db.session.add(g)
    _ledger(sw, account.id, type_='debit', category='gift_sent', amount=cash_value,
            description=f'Sent {gift.name} {gift.icon or ""}'.strip(),
            extra={'coins': price, 'gift_code': gift.code, 'recipient_id': recipient_id})

    # Credit recipient redeemable under lock.
    rw = _wallet(recipient_id, lock=True)
    rw.redeemable = float(rw.redeemable or 0) + net
    _ledger(rw, recipient_id, type_='credit', category='gift_received', amount=net,
            description=f'Received {gift.name} {gift.icon or ""}'.strip(),
            extra={'gift_code': gift.code, 'sender_id': account.id,
                   'gross_ugx': cash_value, 'fee_ugx': fee})

    db.session.commit()
    return success_response('Gift sent!', {
        'gift': g.to_dict(),
        'coins_left': int(sw.coins),
    })


@gifts_bp.route('/received', methods=['GET'])
@lu_jwt_required
def received(account):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    q = Gift.query.filter_by(recipient_id=account.id)\
        .order_by(Gift.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(q, page, per_page)
    return paginated_response([g.to_dict() for g in items], total, page, per_page,
                              'Gifts received.')


@gifts_bp.route('/sent', methods=['GET'])
@lu_jwt_required
def sent(account):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    q = Gift.query.filter_by(sender_id=account.id).order_by(Gift.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(q, page, per_page)
    return paginated_response([g.to_dict() for g in items], total, page, per_page,
                              'Gifts sent.')


@gifts_bp.route('/redeem', methods=['POST'])
@lu_jwt_required
@idempotent
def redeem(account):
    """Move all redeemable gift earnings into withdrawable wallet cash."""
    w = _wallet(account.id, lock=True)
    redeemable = float(w.redeemable or 0)
    if redeemable <= 0:
        db.session.rollback()
        return error_response('Nothing to redeem yet.')
    w.balance = float(w.balance or 0) + redeemable
    w.redeemable = 0.00
    w.total_credited = float(w.total_credited or 0) + redeemable
    _ledger(w, account.id, type_='credit', category='gift_redeem', amount=redeemable,
            description='Redeemed gift earnings to wallet')
    # balance changed → fix the ledger row's balance_after for this credit
    db.session.flush()
    last = WalletTransaction.query.filter_by(
        account_id=account.id, category='gift_redeem')\
        .order_by(WalletTransaction.created_at.desc()).first()
    if last:
        last.balance_after = float(w.balance)
    db.session.commit()
    return success_response('Redeemed to wallet.', {
        'redeemed_ugx': redeemable, 'balance_ugx': float(w.balance),
    })
