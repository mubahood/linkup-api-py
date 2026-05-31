"""
Safety routes: /v1/safety/*
"""
import uuid
from flask import Blueprint, request
from backend.models import db
from backend.domains.safety.models import Report, Block
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.utils.response import success_response, error_response

safety_bp = Blueprint('v1_safety', __name__, url_prefix='/v1/safety')


@safety_bp.route('/report', methods=['POST'])
@lu_jwt_required
def file_report(account):
    data = request.get_json(silent=True) or {}
    target_id = (data.get('target_account_id') or '').strip()
    if not target_id:
        return error_response('target_account_id is required.')
    reason = data.get('reason', 'other')
    if reason not in ('spam', 'harassment', 'fake_profile', 'inappropriate_content', 'scam', 'other'):
        return error_response('Invalid reason.')

    report = Report(
        id=str(uuid.uuid4()),
        reporter_id=account.id,
        target_account_id=target_id,
        target_content_type=data.get('target_content_type'),
        target_content_id=data.get('target_content_id'),
        reason=reason,
        detail=data.get('detail'),
    )
    db.session.add(report)
    db.session.commit()
    return success_response('Report submitted. Our team will review it shortly.', report.to_dict(), status_code=201)


@safety_bp.route('/block', methods=['POST'])
@lu_jwt_required
def block_account(account):
    data = request.get_json(silent=True) or {}
    blocked_id = (data.get('blocked_id') or '').strip()
    if not blocked_id:
        return error_response('blocked_id is required.')
    if blocked_id == account.id:
        return error_response('You cannot block yourself.')
    existing = Block.query.filter_by(blocker_id=account.id, blocked_id=blocked_id).first()
    if existing:
        return error_response('You have already blocked this account.')
    block = Block(id=str(uuid.uuid4()), blocker_id=account.id, blocked_id=blocked_id)
    db.session.add(block)
    db.session.commit()
    return success_response('Account blocked.', block.to_dict(), status_code=201)


@safety_bp.route('/block/<block_id>', methods=['DELETE'])
@lu_jwt_required
def unblock_account(account, block_id):
    block = Block.query.filter_by(id=block_id, blocker_id=account.id).first()
    if not block:
        # Try by blocked_id too
        block = Block.query.filter_by(blocker_id=account.id, blocked_id=block_id).first()
    if not block:
        return error_response('Block not found.', status_code=404)
    db.session.delete(block)
    db.session.commit()
    return success_response('Account unblocked.')


@safety_bp.route('/blocks', methods=['GET'])
@lu_jwt_required
def list_blocks(account):
    blocks = Block.query.filter_by(blocker_id=account.id).order_by(Block.created_at.desc()).all()
    return success_response('Blocks loaded.', [b.to_dict() for b in blocks])
