"""
Wallet routes: /v1/wallet/*

Economy (TikTok-style):
  • Deposit  → buy COINS via Flutterwave (money in).
  • Coins    → spent on gifts (see gift_routes).
  • Gifts    → recipient accrues REDEEMABLE cash (90% of face value).
  • Redeem   → redeemable → withdrawable `balance`.
  • Withdraw → mobile-money payout via Flutterwave Transfers (money out).

All balance mutations row-lock the wallet and write an auditable ledger row.
"""
import uuid
from datetime import datetime
from flask import Blueprint, request, current_app
from backend.models import db
from backend.domains.wallet.models import WalletAccount, WalletTransaction, Withdrawal
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.idempotency import idempotent
from backend.shared.utils.response import success_response, error_response, paginated_response
from backend.shared.utils.pagination import paginate_query

wallet_bp = Blueprint('v1_wallet', __name__, url_prefix='/v1/wallet')


# ── helpers ──────────────────────────────────────────────────────────────────

def _cfg(key, default):
    return current_app.config.get(key, default)


def _get_or_create_wallet(account_id: str, lock: bool = False) -> WalletAccount:
    q = WalletAccount.query.filter_by(account_id=account_id)
    if lock:
        q = q.with_for_update()
    wallet = q.first()
    if not wallet:
        wallet = WalletAccount(id=str(uuid.uuid4()), account_id=account_id,
                               balance=0.00, currency='UGX')
        db.session.add(wallet)
        db.session.commit()
        if lock:
            wallet = WalletAccount.query.filter_by(
                account_id=account_id).with_for_update().first()
    return wallet


def _ledger(wallet, account_id, *, type_, category, amount, balance_after,
            reference=None, description=None, status='completed',
            flw_tx_id=None, extra=None):
    tx = WalletTransaction(
        id=str(uuid.uuid4()), wallet_id=wallet.id, account_id=account_id,
        type=type_, category=category, amount=amount,
        balance_before=float(wallet.balance), balance_after=balance_after,
        reference=reference, description=description, status=status,
        flw_tx_id=flw_tx_id, extra_data=extra,
    )
    db.session.add(tx)
    return tx


# ── balance + history ────────────────────────────────────────────────────────

@wallet_bp.route('/balance', methods=['GET'])
@lu_jwt_required
def balance(account):
    wallet = _get_or_create_wallet(account.id)
    return success_response('Wallet loaded.', wallet.to_dict())


@wallet_bp.route('/transactions', methods=['GET'])
@lu_jwt_required
def transactions(account):
    wallet = _get_or_create_wallet(account.id)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    tx_type = request.args.get('type', '')
    query = WalletTransaction.query.filter_by(wallet_id=wallet.id)
    if tx_type in ('credit', 'debit'):
        query = query.filter(WalletTransaction.type == tx_type)
    query = query.order_by(WalletTransaction.created_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([t.to_dict() for t in items], total, page, per_page,
                              'Transactions loaded.')


# ── deposit (buy coins) ──────────────────────────────────────────────────────

@wallet_bp.route('/topup', methods=['POST'])
@lu_jwt_required
def topup(account):
    """Buy coins with mobile money / card. Body: { amount: UGX }.
    Returns a Flutterwave hosted-payment link; coins are credited only after the
    payment is verified (webhook or redirect-verify)."""
    data = request.get_json(silent=True) or {}
    amount = data.get('amount', 0)
    min_topup = _cfg('MIN_TOPUP_UGX', 500)
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return error_response('Invalid amount.')
    if amount < min_topup:
        return error_response(f'Minimum top-up is UGX {min_topup:,.0f}.')

    wallet = _get_or_create_wallet(account.id)
    tx_ref = f'LU-TOPUP-{uuid.uuid4().hex[:10].upper()}'
    coin_rate = _cfg('COIN_RATE_UGX', 50)
    coins = int(amount // coin_rate)

    # Pending ledger row (no balance change yet — coins credit on verify).
    _ledger(wallet, account.id, type_='credit', category='coin_purchase',
            amount=amount, balance_after=float(wallet.balance), reference=tx_ref,
            description=f'Buy {coins} coins', status='pending',
            extra={'coins': coins, 'kind': 'topup'})
    db.session.commit()

    try:
        from backend.services.flutterwave_service import FlutterwaveService
        flw = FlutterwaveService()
        redirect_url = (_cfg('APP_URL', 'http://localhost:5001')
                        + f'/v1/wallet/topup/{tx_ref}/verify')
        result = flw.initialize_payment(
            amount=amount, tx_ref=tx_ref,
            customer_name=account.display_name or account.handle,
            customer_email=account.email or f'{account.handle}@linkup.app',
            customer_phone=account.phone or '',
            redirect_url=redirect_url, currency='UGX',
            description=f'LinkUp coins ({coins})',
            meta={'account_id': account.id, 'kind': 'topup', 'coins': coins},
        )
        return success_response('Payment link created.', {
            'tx_ref': tx_ref, 'payment_link': result['payment_link'],
            'amount': amount, 'coins': coins, 'currency': 'UGX',
        })
    except Exception as e:
        return error_response(
            f'Payment provider unavailable. Reference {tx_ref}. {e}', status_code=502)


def _complete_topup(tx) -> dict:
    """Idempotently credit coins for a verified pending top-up tx (under lock)."""
    if tx.status == 'completed':
        return {'already': True}
    wallet = WalletAccount.query.filter_by(
        account_id=tx.account_id).with_for_update().first()
    coins = int((tx.extra_data or {}).get('coins') or 0)
    wallet.coins = int(wallet.coins or 0) + coins
    wallet.total_credited = float(wallet.total_credited or 0) + float(tx.amount)
    tx.status = 'completed'
    tx.balance_after = float(wallet.balance)
    db.session.commit()
    return {'coins_added': coins, 'coins': int(wallet.coins)}


@wallet_bp.route('/topup/<tx_ref>/verify', methods=['GET', 'POST'])
@lu_jwt_required
@idempotent
def verify_topup(account, tx_ref):
    """Verify a top-up after the Flutterwave redirect and credit coins."""
    tx = WalletTransaction.query.filter_by(
        reference=tx_ref, account_id=account.id).first()
    if not tx:
        return error_response('Transaction not found.', status_code=404)
    if tx.status == 'completed':
        wallet = _get_or_create_wallet(account.id)
        return success_response('Already credited.', {'coins': int(wallet.coins)})

    flw_tx_id = (request.args.get('transaction_id')
                 or (request.get_json(silent=True) or {}).get('transaction_id', ''))
    verified = False
    if flw_tx_id and flw_tx_id != 'DEV_BYPASS':
        try:
            from backend.services.flutterwave_service import FlutterwaveService
            flw = FlutterwaveService()
            resp = flw.verify_by_id(flw_tx_id)
            if (flw.is_payment_successful(resp, float(tx.amount), 'UGX')
                    and resp.get('data', {}).get('tx_ref') == tx_ref):
                verified = True
                tx.flw_tx_id = str(flw_tx_id)
        except Exception:
            verified = False

    # DEV_BYPASS only outside production, for internal testing without real money.
    if not verified and flw_tx_id == 'DEV_BYPASS' and current_app.config.get('DEBUG'):
        verified = True

    if not verified:
        return error_response('Payment not verified yet.', status_code=422)

    result = _complete_topup(tx)
    return success_response('Top-up successful.', result)


# ── convert coins → withdrawable cash ────────────────────────────────────────

@wallet_bp.route('/coins/redeem', methods=['POST'])
@lu_jwt_required
@idempotent
def redeem_coins(account):
    """Convert coins into withdrawable cash at COIN_RATE_UGX.
    Body: { coins?: int }  — omit to convert all coins."""
    data = request.get_json(silent=True) or {}
    rate = float(_cfg('COIN_RATE_UGX', 50))

    wallet = _get_or_create_wallet(account.id, lock=True)
    avail = int(wallet.coins or 0)

    raw = data.get('coins')
    if raw is None:
        coins = avail
    else:
        try:
            coins = int(raw)
        except (TypeError, ValueError):
            db.session.rollback()
            return error_response('Invalid coin amount.')

    if coins <= 0:
        db.session.rollback()
        return error_response('You have no coins to convert.')
    if coins > avail:
        db.session.rollback()
        return error_response(f'You only have {avail} coins.')

    cash = round(coins * rate, 2)
    new_balance = float(wallet.balance) + cash
    # Ledger BEFORE mutating balance so balance_before is recorded correctly.
    _ledger(wallet, account.id, type_='credit', category='coins_redeem',
            amount=cash, balance_after=new_balance,
            description=f'Converted {coins} coins to cash',
            extra={'coins': coins, 'rate': rate})
    wallet.coins = avail - coins
    wallet.balance = new_balance
    wallet.total_credited = float(wallet.total_credited or 0) + cash
    db.session.commit()
    return success_response('Coins converted to cash.', {
        'coins': int(wallet.coins),
        'balance': float(wallet.balance),
        'cash_added': cash,
    })


# ── withdrawals (payout) ─────────────────────────────────────────────────────

@wallet_bp.route('/withdraw/options', methods=['GET'])
@lu_jwt_required
def withdraw_options(account):
    wallet = _get_or_create_wallet(account.id)
    return success_response('Options loaded.', {
        'networks': [{'code': 'MTN', 'label': 'MTN MoMo'},
                     {'code': 'AIRTEL', 'label': 'Airtel Money'}],
        'min_ugx': _cfg('MIN_WITHDRAW_UGX', 1000),
        'fee_ugx': _cfg('WITHDRAW_FEE_UGX', 500),
        'auto_limit_ugx': _cfg('WITHDRAW_AUTO_LIMIT_UGX', 100000),
        'withdrawable_ugx': float(wallet.balance),
    })


@wallet_bp.route('/withdraw', methods=['POST'])
@lu_jwt_required
@idempotent
def withdraw(account):
    """Withdraw withdrawable cash to a mobile-money number.
    Body: { amount: UGX, phone, network: MTN|AIRTEL }."""
    data = request.get_json(silent=True) or {}
    try:
        amount = float(data.get('amount', 0))
    except (TypeError, ValueError):
        return error_response('Invalid amount.')
    phone = (data.get('phone') or '').strip()
    network = (data.get('network') or '').upper().strip()
    fee = float(_cfg('WITHDRAW_FEE_UGX', 500))
    min_wd = float(_cfg('MIN_WITHDRAW_UGX', 1000))
    auto_limit = float(_cfg('WITHDRAW_AUTO_LIMIT_UGX', 100000))

    if not phone:
        return error_response('Phone number is required.')

    # Auto-detect the network from the number so payouts can't be mis-routed.
    from backend.services.flutterwave_service import FlutterwaveService
    detected = FlutterwaveService.detect_network_ug(phone)
    if network and network not in ('MTN', 'AIRTEL'):
        return error_response('Choose MTN or Airtel.')
    if not network:
        network = detected
    if detected and network and detected != network:
        return error_response(
            f'That number looks like {detected}, not {network}. '
            f'Please select {detected}.')
    if not network:
        return error_response(
            'Couldn’t recognise that mobile number. Check it and try again.')
    if amount < min_wd:
        return error_response(f'Minimum withdrawal is UGX {min_wd:,.0f}.')

    total = amount + fee
    # Lock wallet, check & debit atomically.
    wallet = _get_or_create_wallet(account.id, lock=True)
    if float(wallet.balance) < total:
        db.session.rollback()
        return error_response(
            f'Insufficient balance. You need UGX {total:,.0f} (incl. UGX {fee:,.0f} fee).')

    ref = f'LU-WD-{uuid.uuid4().hex[:12].upper()}'
    net = amount  # beneficiary receives `amount`; fee is platform's
    wd = Withdrawal(
        id=str(uuid.uuid4()), account_id=account.id, amount_ugx=amount,
        fee_ugx=fee, net_ugx=net, phone=phone, network=network,
        beneficiary_name=account.display_name or account.handle,
        flw_reference=ref,
        status='review' if amount >= auto_limit else 'processing',
    )
    db.session.add(wd)

    wallet.balance = float(wallet.balance) - total
    wallet.total_debited = float(wallet.total_debited or 0) + total
    _ledger(wallet, account.id, type_='debit', category='withdrawal',
            amount=total, balance_after=float(wallet.balance), reference=ref,
            description=f'Withdraw UGX {amount:,.0f} to {network} {phone} (fee {fee:,.0f})',
            status='pending', extra={'withdrawal_id': wd.id})
    db.session.commit()

    # Manual review for large amounts — stop here; admin releases later.
    if wd.status == 'review':
        return success_response('Withdrawal received — under review for payout.',
                                wd.to_dict())

    # Auto payout via Flutterwave Transfers.
    try:
        from backend.services.flutterwave_service import FlutterwaveService
        flw = FlutterwaveService()
        res = flw.initiate_mobile_money_payout_ug(
            phone=phone, network=network, amount=amount,
            beneficiary_name=wd.beneficiary_name,
            narration='LinkUp withdrawal', reference=ref)
        wd.flw_transfer_id = res.get('flw_transfer_id')
        wd.status = 'processing'
        db.session.commit()
        return success_response('Withdrawal initiated.', wd.to_dict())
    except Exception as e:
        # Payout call failed — reverse the debit so funds aren't lost.
        _reverse_withdrawal(wd, reason=f'Payout init failed: {e}')
        return error_response(
            'Could not start the payout. Your balance was not charged.',
            status_code=502)


def _reverse_withdrawal(wd: Withdrawal, reason: str):
    """Refund a failed withdrawal back to the wallet (idempotent on status)."""
    if wd.status in ('reversed', 'paid'):
        return
    wallet = WalletAccount.query.filter_by(
        account_id=wd.account_id).with_for_update().first()
    refund = float(wd.amount_ugx) + float(wd.fee_ugx or 0)
    wallet.balance = float(wallet.balance) + refund
    wallet.total_debited = max(0.0, float(wallet.total_debited or 0) - refund)
    wd.status = 'reversed'
    wd.failure_reason = (reason or '')[:300]
    wd.settled_at = datetime.utcnow()
    _ledger(wallet, wd.account_id, type_='credit', category='withdrawal_reversal',
            amount=refund, balance_after=float(wallet.balance),
            reference=wd.flw_reference, description='Withdrawal reversed',
            status='completed', extra={'withdrawal_id': wd.id})
    db.session.commit()


@wallet_bp.route('/withdrawals', methods=['GET'])
@lu_jwt_required
def withdrawals(account):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = Withdrawal.query.filter_by(account_id=account.id)\
        .order_by(Withdrawal.requested_at.desc())
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([w.to_dict() for w in items], total, page, per_page,
                              'Withdrawals loaded.')


# ── Flutterwave webhook (collections + transfers) ────────────────────────────

@wallet_bp.route('/webhook/flutterwave', methods=['POST'])
def flutterwave_webhook():
    """Public webhook. Verifies the `verif-hash` header, then settles
    collections (credit coins) and transfers (settle withdrawals)."""
    from backend.services.flutterwave_service import FlutterwaveService
    flw = FlutterwaveService()
    received = request.headers.get('verif-hash') or request.headers.get('verifi-hash')
    if not flw.verify_webhook_hash(received):
        return error_response('Invalid signature.', status_code=401)

    payload = request.get_json(silent=True) or {}
    event = (payload.get('event') or '').lower()
    data = payload.get('data') or {}

    try:
        # Collections — credit coins on a successful charge.
        if 'charge' in event or data.get('tx_ref', '').startswith('LU-TOPUP-'):
            tx_ref = data.get('tx_ref')
            status = (data.get('status') or '').lower()
            tx = WalletTransaction.query.filter_by(reference=tx_ref).first()
            if tx and tx.status == 'pending' and status == 'successful':
                # Re-verify server-side before crediting.
                ok = False
                try:
                    resp = flw.verify_by_id(str(data.get('id')))
                    ok = flw.is_payment_successful(resp, float(tx.amount), 'UGX')
                except Exception:
                    ok = False
                if ok:
                    tx.flw_tx_id = str(data.get('id'))
                    _complete_topup(tx)

        # Transfers — settle a withdrawal.
        elif 'transfer' in event:
            ref = data.get('reference')
            status = (data.get('status') or '').upper()
            wd = Withdrawal.query.filter_by(flw_reference=ref).first()
            if wd and wd.status not in ('paid', 'reversed'):
                if status == 'SUCCESSFUL':
                    wd.status = 'paid'
                    wd.settled_at = datetime.utcnow()
                    wd.flw_transfer_id = str(data.get('id') or wd.flw_transfer_id)
                    db.session.commit()
                elif status in ('FAILED', 'ERROR'):
                    _reverse_withdrawal(wd, reason=data.get('complete_message')
                                        or 'Transfer failed')
    except Exception:
        db.session.rollback()

    # Always 200 so Flutterwave doesn't retry forever on our errors.
    return success_response('ok')
