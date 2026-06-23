"""
Endorsements routes: /v1/endorsements/*

Per CORE_DATA_MODEL.md §5.3:
An endorsement is a skill-level recommendation from one account to another.
Endorsers must be direct Links (accepted connections).
"""
import uuid
from flask import Blueprint, request
from backend.models import db
from backend.domains.interest.models import InterestTag
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.utils.response import success_response, error_response, paginated_response
from backend.shared.utils.pagination import paginate_query

endorsements_bp = Blueprint('v1_endorsements', __name__, url_prefix='/v1/endorsements')


class Endorsement(db.Model):
    __tablename__ = 'lu_endorsements'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    endorser_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    endorsee_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    tag_id = db.Column(db.String(36), db.ForeignKey('lu_interest_tags.id', ondelete='CASCADE'), nullable=False)
    body = db.Column(db.Text, nullable=True)
    weight = db.Column(db.Numeric(3, 2), default=0.50)
    created_at = db.Column(db.DateTime, default=lambda: __import__('datetime').datetime.utcnow())

    endorser = db.relationship('Account', foreign_keys=[endorser_id], lazy='joined')
    endorsee = db.relationship('Account', foreign_keys=[endorsee_id], lazy='joined')
    tag = db.relationship('InterestTag', foreign_keys=[tag_id], lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'endorser_id': self.endorser_id,
            'endorsee_id': self.endorsee_id,
            'tag_id': self.tag_id,
            'body': self.body,
            'weight': float(self.weight or 0.5),
            'endorser': self.endorser.to_dict() if self.endorser else None,
            'tag': self.tag.to_dict() if self.tag else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


@endorsements_bp.route('', methods=['POST'])
@lu_jwt_required
def create_endorsement(account):
    """Endorse a connection's skill."""
    from backend.domains.links.models import Link
    from backend.domains.interest.models import InterestTag
    from sqlalchemy import or_
    data = request.get_json(silent=True) or {}
    endorsee_id = (data.get('endorsee_id') or '').strip()
    tag_id = (data.get('tag_id') or '').strip()
    body = (data.get('body') or '').strip()

    if not endorsee_id or not tag_id:
        return error_response('endorsee_id and tag_id are required.')
    if endorsee_id == account.id:
        return error_response('You cannot endorse yourself.')

    # Must be a direct Link to endorse
    link = Link.query.filter(
        or_(
            (Link.requester_id == account.id) & (Link.addressee_id == endorsee_id),
            (Link.requester_id == endorsee_id) & (Link.addressee_id == account.id),
        ),
        Link.status == 'accepted',
    ).first()
    if not link:
        return error_response('You can only endorse your direct connections.')

    tag = db.session.get(InterestTag, tag_id)
    if not tag:
        return error_response('Interest tag not found.', status_code=404)

    existing = Endorsement.query.filter_by(
        endorser_id=account.id, endorsee_id=endorsee_id, tag_id=tag_id
    ).first()
    if existing:
        return error_response('You have already endorsed this skill for this person.')

    endorsement = Endorsement(
        id=str(uuid.uuid4()),
        endorser_id=account.id,
        endorsee_id=endorsee_id,
        tag_id=tag_id,
        body=body or None,
        weight=0.75,  # endorsements from connections carry high weight
    )
    db.session.add(endorsement)
    db.session.commit()

    # Notify endorsee
    try:
        from backend.domains.notifications.service import create_notification
        create_notification(
            account_id=endorsee_id,
            notif_type='endorsement.received',
            title=f'{account.display_name} endorsed your {tag.display_name_en}',
            body=body[:80] if body else f'{account.display_name} thinks you are skilled in {tag.display_name_en}.',
            data={'endorsement_id': endorsement.id, 'tag_id': tag_id},
            action_url=f'/profile/@{account.handle}',
        )
    except Exception:
        pass

    return success_response('Endorsement created.', endorsement.to_dict(), status_code=201)


@endorsements_bp.route('/received', methods=['GET'])
@lu_jwt_required
def my_endorsements(account):
    """Endorsements I have received."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = Endorsement.query.filter_by(endorsee_id=account.id).order_by(
        Endorsement.created_at.desc()
    )
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([e.to_dict() for e in items], total, page, per_page, 'Endorsements loaded.')


@endorsements_bp.route('/@<handle>', methods=['GET'])
@lu_jwt_required
def account_endorsements(account, handle):
    """Endorsements received by a specific account (public)."""
    from backend.domains.identity.models import Account
    normalized = handle.lower().replace('-', '_')
    target = Account.query.filter(
        Account.handle.ilike(normalized),
        Account.deleted_at.is_(None),
    ).first()
    if not target:
        return error_response('Account not found.', status_code=404)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = Endorsement.query.filter_by(endorsee_id=target.id).order_by(
        Endorsement.created_at.desc()
    )
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([e.to_dict() for e in items], total, page, per_page, 'Endorsements loaded.')


@endorsements_bp.route('/<endorsement_id>', methods=['DELETE'])
@lu_jwt_required
def delete_endorsement(account, endorsement_id):
    """Withdraw an endorsement you gave."""
    endorsement = Endorsement.query.filter_by(
        id=endorsement_id, endorser_id=account.id
    ).first()
    if not endorsement:
        return error_response('Endorsement not found.', status_code=404)
    db.session.delete(endorsement)
    db.session.commit()
    return success_response('Endorsement withdrawn.')
