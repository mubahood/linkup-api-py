"""
Identity routes: /v1/auth/*
"""
import logging
from flask import Blueprint, request
from backend.models import db

logger = logging.getLogger(__name__)
from backend.domains.identity.models import Account, RefreshToken
from backend.domains.identity.service import (
    create_otp, verify_otp, create_account, issue_tokens, _hash_code
)
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.utils.response import success_response, error_response

identity_bp = Blueprint('v1_identity', __name__, url_prefix='/v1/auth')


@identity_bp.route('/register', methods=['POST'])
def register():
    """Register: phone + display_name → sends OTP."""
    data = request.get_json(silent=True) or {}
    phone = (data.get('phone') or '').strip()
    display_name = (data.get('display_name') or '').strip()

    if not phone:
        return error_response('Phone number is required.')
    if not display_name:
        return error_response('Display name is required.')

    # Check existing account
    existing = Account.query.filter_by(phone=phone).first()
    if existing and existing.deleted_at is None:
        return error_response('An account with this phone number already exists.')

    # Create OTP
    code = create_otp(phone, purpose='register')

    # In real prod, send SMS here
    logger.info(f'[Register] OTP for {phone}: {code} (dev mode)')

    return success_response('OTP sent to your phone. Please verify to complete registration.', {
        'phone': phone,
        'display_name': display_name,
    }, status_code=200)


@identity_bp.route('/otp/verify', methods=['POST'])
def otp_verify():
    """Verify OTP → create account if needed, return tokens."""
    data = request.get_json(silent=True) or {}
    phone = (data.get('phone') or '').strip()
    code = (data.get('code') or '').strip()
    display_name = (data.get('display_name') or '').strip()

    if not phone or not code:
        return error_response('Phone and code are required.')

    # Try register purpose first, then login
    success, msg = verify_otp(phone, code, purpose='register')
    if not success:
        success, msg = verify_otp(phone, code, purpose='login')
    if not success:
        return error_response(msg)

    # Get or create account
    account = Account.query.filter_by(phone=phone).filter(
        Account.deleted_at.is_(None)
    ).first()

    if not account:
        # Check for a soft-deleted account with the same phone — reactivate it
        deleted = Account.query.filter_by(phone=phone).filter(
            Account.deleted_at.isnot(None)
        ).first()
        if deleted:
            deleted.deleted_at = None
            deleted.account_status = 'active'
            deleted.phone_verified = 1
            if display_name and display_name != deleted.display_name:
                deleted.display_name = display_name
            db.session.commit()
            account = deleted
            is_new = True
        else:
            resolved_name = display_name or f'Member {phone[-4:]}'
            account = create_account(phone, resolved_name)
            is_new = True
    else:
        account.phone_verified = 1
        db.session.commit()
        is_new = False

    tokens = issue_tokens(account)
    payload = {**account.to_dict(), **tokens, 'is_new_account': is_new}
    return success_response('Verification successful.', payload)


@identity_bp.route('/otp/request', methods=['POST'])
def otp_request():
    """Request / resend OTP."""
    data = request.get_json(silent=True) or {}
    phone = (data.get('phone') or '').strip()
    purpose = data.get('purpose', 'login')

    if not phone:
        return error_response('Phone number is required.')

    code = create_otp(phone, purpose=purpose)
    # In production, send SMS here
    return success_response('OTP sent to your phone.')


@identity_bp.route('/login', methods=['POST'])
def login():
    """Login via OTP (primary) or password (fallback)."""
    data = request.get_json(silent=True) or {}
    phone = (data.get('phone') or '').strip()
    code = (data.get('code') or '').strip()
    password = (data.get('password') or '').strip()

    if not phone:
        return error_response('Phone number is required.')

    account = Account.query.filter_by(phone=phone).filter(
        Account.deleted_at.is_(None)
    ).first()

    if not account:
        return error_response('No account found with this phone number.')

    if account.account_status != 'active':
        return error_response('Your account has been suspended.')

    if code:
        # OTP login
        success, msg = verify_otp(phone, code, purpose='login')
        if not success:
            return error_response(msg)
    elif password:
        # Password fallback
        if not account.check_password(password):
            return error_response('Invalid credentials.')
    else:
        # No credentials — send OTP and ask for it
        create_otp(phone, purpose='login')
        return success_response('OTP sent to your phone.', {'requires_otp': True, 'phone': phone})

    tokens = issue_tokens(account)
    return success_response('Login successful.', {**account.to_dict(), **tokens})


@identity_bp.route('/me', methods=['GET'])
@lu_jwt_required
def me(account):
    """Get current authenticated account."""
    return success_response('Account loaded.', account.to_dict())


@identity_bp.route('/logout', methods=['POST'])
@lu_jwt_required
def logout(account):
    """Invalidate refresh token."""
    data = request.get_json(silent=True) or {}
    refresh_token = data.get('refresh_token', '')
    if refresh_token:
        from datetime import datetime
        rt = RefreshToken.query.filter_by(
            account_id=account.id,
            token_hash=_hash_code(refresh_token)
        ).first()
        if rt:
            rt.revoked_at = datetime.utcnow()
            db.session.commit()
    return success_response('Logged out successfully.')


@identity_bp.route('/device', methods=['POST'])
@lu_jwt_required
def register_device(account):
    """Register or update a device token for push notifications."""
    data = request.get_json(silent=True) or {}
    player_id = (data.get('onesignal_player_id') or '').strip()
    platform = data.get('platform', 'android')
    device_token = data.get('device_token', '')

    if not player_id:
        return error_response('onesignal_player_id is required.')

    from backend.domains.identity.models import AccountDevice
    device = AccountDevice.query.filter_by(
        account_id=account.id, onesignal_player_id=player_id
    ).first()
    if device:
        device.platform = platform
        if device_token:
            device.device_token = device_token
    else:
        device = AccountDevice(
            id=str(__import__('uuid').uuid4()),
            account_id=account.id,
            onesignal_player_id=player_id,
            platform=platform,
            device_token=device_token or None,
        )
        db.session.add(device)
    db.session.commit()
    return success_response('Device registered.', {
        'id': device.id,
        'platform': device.platform,
        'onesignal_player_id': device.onesignal_player_id,
    })


@identity_bp.route('/refresh', methods=['POST'])
def refresh():
    """Exchange refresh token for a new access token."""
    from datetime import datetime
    from flask_jwt_extended import create_access_token
    data = request.get_json(silent=True) or {}
    raw_token = (data.get('refresh_token') or '').strip()
    if not raw_token:
        return error_response('refresh_token is required.', status_code=401)

    rt = RefreshToken.query.filter_by(
        token_hash=_hash_code(raw_token)
    ).filter(
        RefreshToken.revoked_at.is_(None),
        RefreshToken.expires_at > datetime.utcnow(),
    ).first()

    if not rt:
        return error_response('Invalid or expired refresh token.', status_code=401)

    account = db.session.get(Account, rt.account_id)
    if not account or account.account_status != 'active':
        return error_response('Account not found or suspended.', status_code=401)

    access_token = create_access_token(identity=account.id)
    return success_response('Token refreshed.', {
        'access_token': access_token,
        'token_type': 'Bearer',
    })



