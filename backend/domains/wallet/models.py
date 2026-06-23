"""Wallet domain models: WalletAccount, WalletTransaction."""
import uuid
from datetime import datetime
from backend.models import db


class WalletAccount(db.Model):
    __tablename__ = 'lu_wallet_accounts'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'),
                           nullable=False, unique=True)
    balance = db.Column(db.Numeric(14, 2), nullable=False, default=0.00)   # withdrawable cash
    coins = db.Column(db.Integer, nullable=False, default=0)               # bought, spend-only
    redeemable = db.Column(db.Numeric(14, 2), nullable=False, default=0.00)  # gift earnings awaiting redeem
    currency = db.Column(db.String(5), default='UGX')
    total_credited = db.Column(db.Numeric(14, 2), default=0.00)
    total_debited = db.Column(db.Numeric(14, 2), default=0.00)
    flw_customer_id = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'balance': float(self.balance),
            'coins': int(self.coins or 0),
            'redeemable': float(self.redeemable or 0),
            'currency': self.currency,
            'total_credited': float(self.total_credited or 0),
            'total_debited': float(self.total_debited or 0),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class WalletTransaction(db.Model):
    __tablename__ = 'lu_wallet_transactions'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    wallet_id = db.Column(db.String(36), db.ForeignKey('lu_wallet_accounts.id', ondelete='CASCADE'),
                          nullable=False)
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'),
                           nullable=False)
    type = db.Column(db.String(10), nullable=False)
    category = db.Column(db.String(50), default='topup')
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    balance_before = db.Column(db.Numeric(14, 2), default=0.00)
    balance_after = db.Column(db.Numeric(14, 2), default=0.00)
    reference = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='completed')
    flw_tx_id = db.Column(db.String(100), nullable=True)
    extra_data = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Which "pot" a transaction moves — so the app can show the right unit and
    # only sum CASH rows against the withdrawable balance.
    _CASH_CATS = {'coins_redeem', 'gift_redeem', 'withdrawal', 'withdrawal_reversal'}
    _COIN_CATS = {'coin_purchase', 'gift_sent'}
    _EARN_CATS = {'gift_received'}

    def _affects(self):
        if self.category in self._COIN_CATS:
            return 'coins'
        if self.category in self._EARN_CATS:
            return 'earnings'
        return 'cash'

    def to_dict(self):
        extra = self.extra_data if isinstance(self.extra_data, dict) else {}
        return {
            'id': self.id,
            'type': self.type,
            'category': self.category,
            'affects': self._affects(),       # 'cash' | 'coins' | 'earnings'
            'amount': float(self.amount),
            'coins': extra.get('coins'),      # for coin_purchase / gift_sent
            'balance_before': float(self.balance_before or 0),
            'balance_after': float(self.balance_after or 0),
            'reference': self.reference,
            'description': self.description,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class GiftCatalog(db.Model):
    __tablename__ = 'lu_gift_catalog'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = db.Column(db.String(40), nullable=False, unique=True)
    name = db.Column(db.String(80), nullable=False)
    icon = db.Column(db.String(20), nullable=True)
    price_coins = db.Column(db.Integer, nullable=False)
    cash_value_ugx = db.Column(db.Numeric(14, 2), nullable=False)
    sort_order = db.Column(db.SmallInteger, default=0)
    active = db.Column(db.SmallInteger, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'code': self.code,
            'name': self.name,
            'icon': self.icon,
            'price_coins': int(self.price_coins),
            'cash_value_ugx': float(self.cash_value_ugx),
        }


class Gift(db.Model):
    __tablename__ = 'lu_gifts'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sender_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'),
                          nullable=False)
    recipient_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'),
                             nullable=False)
    gift_code = db.Column(db.String(40), nullable=False)
    gift_name = db.Column(db.String(80), nullable=True)
    coins_spent = db.Column(db.Integer, nullable=False)
    cash_value_ugx = db.Column(db.Numeric(14, 2), nullable=False)
    platform_fee_ugx = db.Column(db.Numeric(14, 2), default=0.00)
    net_ugx = db.Column(db.Numeric(14, 2), nullable=False)
    context_type = db.Column(db.String(20), nullable=True)
    context_id = db.Column(db.String(36), nullable=True)
    message = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'recipient_id': self.recipient_id,
            'gift_code': self.gift_code,
            'gift_name': self.gift_name,
            'coins_spent': int(self.coins_spent),
            'cash_value_ugx': float(self.cash_value_ugx),
            'net_ugx': float(self.net_ugx),
            'context_type': self.context_type,
            'context_id': self.context_id,
            'message': self.message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Withdrawal(db.Model):
    __tablename__ = 'lu_withdrawals'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'),
                           nullable=False)
    amount_ugx = db.Column(db.Numeric(14, 2), nullable=False)
    fee_ugx = db.Column(db.Numeric(14, 2), default=0.00)
    net_ugx = db.Column(db.Numeric(14, 2), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    network = db.Column(db.String(20), nullable=False)
    beneficiary_name = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(20), default='requested')
    flw_transfer_id = db.Column(db.String(100), nullable=True)
    flw_reference = db.Column(db.String(100), nullable=True, unique=True)
    failure_reason = db.Column(db.String(300), nullable=True)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    settled_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'amount_ugx': float(self.amount_ugx),
            'fee_ugx': float(self.fee_ugx or 0),
            'net_ugx': float(self.net_ugx),
            'phone': self.phone,
            'network': self.network,
            'status': self.status,
            'failure_reason': self.failure_reason,
            'requested_at': self.requested_at.isoformat() if self.requested_at else None,
            'settled_at': self.settled_at.isoformat() if self.settled_at else None,
        }


class PasswordReset(db.Model):
    __tablename__ = 'lu_password_resets'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    phone = db.Column(db.String(30), nullable=False)
    code_hash = db.Column(db.String(500), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
