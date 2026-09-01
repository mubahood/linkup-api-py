"""Subscriptions domain models: SubscriptionPlan (catalog), Subscription (ledger)."""
import uuid
from datetime import datetime
from backend.models import db


class SubscriptionPlan(db.Model):
    __tablename__ = 'lu_subscription_plans'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    app_id = db.Column(db.String(20), nullable=False)
    code = db.Column(db.String(40), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    tagline = db.Column(db.String(160), nullable=True)
    price_ugx = db.Column(db.Numeric(14, 2), nullable=False)
    # Optional time-boxed promo — admin sets both to run a discount without a
    # code change; effective_price_ugx() is what purchase/display should use.
    discount_price_ugx = db.Column(db.Numeric(14, 2), nullable=True)
    discount_ends_at = db.Column(db.DateTime, nullable=True)
    duration_days = db.Column(db.Integer, nullable=False, default=0)
    sort_order = db.Column(db.SmallInteger, default=0)
    active = db.Column(db.SmallInteger, default=1)
    badge_color = db.Column(db.String(20), nullable=True)
    limits = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def is_free(self) -> bool:
        return float(self.price_ugx or 0) <= 0

    @property
    def discount_active(self) -> bool:
        from datetime import datetime
        return (self.discount_price_ugx is not None
                and self.discount_ends_at is not None
                and self.discount_ends_at > datetime.utcnow())

    @property
    def effective_price_ugx(self) -> float:
        """The price to actually charge/display — the discount price while a
        promo is running, otherwise the regular price."""
        if self.discount_active:
            return float(self.discount_price_ugx)
        return float(self.price_ugx)

    def get_limit(self, key: str, default=0):
        limits = self.limits if isinstance(self.limits, dict) else {}
        return limits.get(key, default)

    def to_dict(self):
        return {
            'id': self.id,
            'app_id': self.app_id,
            'code': self.code,
            'name': self.name,
            'tagline': self.tagline,
            'price_ugx': float(self.price_ugx),
            'effective_price_ugx': self.effective_price_ugx,
            'discount_active': self.discount_active,
            'discount_ends_at': self.discount_ends_at.isoformat() if self.discount_ends_at else None,
            'duration_days': int(self.duration_days),
            'sort_order': int(self.sort_order or 0),
            'active': bool(self.active),
            'badge_color': self.badge_color,
            'is_free': self.is_free,
            'limits': self.limits if isinstance(self.limits, dict) else {},
        }


class Subscription(db.Model):
    __tablename__ = 'lu_subscriptions'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'),
                           nullable=False)
    plan_id = db.Column(db.String(36), db.ForeignKey('lu_subscription_plans.id', ondelete='RESTRICT'),
                        nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending|active|expired|cancelled
    starts_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    amount_paid_ugx = db.Column(db.Numeric(14, 2), nullable=False, default=0.00)
    tx_ref = db.Column(db.String(100), nullable=False, unique=True)
    flw_tx_id = db.Column(db.String(100), nullable=True)
    extra_data = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    plan = db.relationship('SubscriptionPlan', foreign_keys=[plan_id], lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'plan': self.plan.to_dict() if self.plan else None,
            'status': self.status,
            'starts_at': self.starts_at.isoformat() if self.starts_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'amount_paid_ugx': float(self.amount_paid_ugx or 0),
            'tx_ref': self.tx_ref,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
