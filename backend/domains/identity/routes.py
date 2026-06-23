"""
Identity routes: /v1/auth/*
Email-primary auth: register and verify via email OTP.
Phone-based flows remain for backward compatibility.
"""
import logging
from flask import Blueprint, request
from backend.shared.ratelimit import rate_limit
from backend.models import db

logger = logging.getLogger(__name__)
from backend.domains.identity.models import Account, RefreshToken
from backend.domains.identity.service import (
    create_otp, verify_otp, create_account, create_account_email,
    issue_tokens, _hash_code
)
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.utils.response import success_response, error_response

identity_bp = Blueprint('v1_identity', __name__, url_prefix='/v1/auth')


@identity_bp.route('/register', methods=['POST'])
def register():
    """Register: email (or phone) + display_name → sends OTP."""
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    phone = (data.get('phone') or '').strip()
    display_name = (data.get('display_name') or '').strip()

    identifier = email or phone
    if not identifier:
        return error_response('Email address is required.')

    if email:
        existing = Account.query.filter_by(email=email).filter(
            Account.deleted_at.is_(None)
        ).first()
        if existing:
            return error_response('An account with this email already exists.')
        code = create_otp(email, purpose='register')
        try:
            from backend.shared.email.service import send_otp_email
            name = display_name or email.split('@')[0]
            send_otp_email(email, name, code, 'register')
        except Exception as e:
            logger.error(f'[Register] email send failed: {e}')
        logger.info(f'[Register] OTP for {email}: {code} (dev)')
        return success_response('Verification code sent to your email.', {'email': email})
    else:
        existing = Account.query.filter_by(phone=phone).filter(
            Account.deleted_at.is_(None)
        ).first()
        if existing:
            return error_response('An account with this phone number already exists.')
        code = create_otp(phone, purpose='register')
        logger.info(f'[Register] OTP for {phone}: {code} (dev)')
        return success_response('OTP sent to your phone.', {'phone': phone})


@identity_bp.route('/otp/request', methods=['POST'])
@rate_limit(20, 60, body_field='phone')  # per-phone OTP cap (T-API-071)
def otp_request():
    """
    Request / resend OTP.
    Body: { email?, phone?, purpose? }
    Sends code to email if email provided, SMS if phone provided.
    """
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    phone = (data.get('phone') or '').strip()
    purpose = data.get('purpose', 'login')
    medium = (data.get('medium') or '').strip().lower()

    identifier = email or phone
    if not identifier:
        return error_response('Email or phone number is required.')

    # medium='email' requested by phone: resolve the account's email and route
    # to it. If the account has no email on file, reject clearly rather than
    # silently falling back to SMS (T-API-043).
    if medium == 'email' and not email and phone:
        account = Account.query.filter_by(phone=phone).filter(
            Account.deleted_at.is_(None)
        ).first()
        if not account or not account.email:
            return error_response('No email address on file for this account. '
                                  'Add an email first or use phone OTP.')
        email = account.email.strip().lower()
        identifier = email

    code = create_otp(identifier, purpose=purpose)

    if email:
        try:
            from backend.shared.email.service import send_otp_email
            account = Account.query.filter_by(email=email).filter(
                Account.deleted_at.is_(None)
            ).first()
            name = account.display_name if account else email.split('@')[0]
            send_otp_email(email, name, code, purpose)
        except Exception as e:
            logger.error(f'[OTP] email send failed: {e}')
        logger.info(f'[OTP] {email} → {code} (purpose={purpose})')
        return success_response(f'Verification code sent to {email}.')
    else:
        logger.info(f'[OTP] {phone} → {code} (purpose={purpose})')
        return success_response('OTP sent to your phone.')


@identity_bp.route('/otp/verify', methods=['POST'])
def otp_verify():
    """Verify OTP → create account if needed, return tokens."""
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    phone = (data.get('phone') or '').strip()
    code = (data.get('code') or '').strip()
    display_name = (data.get('display_name') or '').strip()

    identifier = email or phone
    if not identifier or not code:
        return error_response('Email (or phone) and code are required.')

    # Try register purpose first, then login
    ok, msg = verify_otp(identifier, code, purpose='register')
    if not ok:
        ok, msg = verify_otp(identifier, code, purpose='login')
    if not ok:
        return error_response(msg)

    # Find account by email or phone
    if email:
        account = Account.query.filter_by(email=email).filter(
            Account.deleted_at.is_(None)
        ).first()
        deleted = (None if account else
                   Account.query.filter_by(email=email).filter(
                       Account.deleted_at.isnot(None)
                   ).first())
    else:
        account = Account.query.filter_by(phone=phone).filter(
            Account.deleted_at.is_(None)
        ).first()
        deleted = (None if account else
                   Account.query.filter_by(phone=phone).filter(
                       Account.deleted_at.isnot(None)
                   ).first())

    is_new = False
    if not account:
        if deleted:
            deleted.deleted_at = None
            deleted.account_status = 'active'
            deleted.kyc_level = 0
            if email:
                deleted.email_verified = 1
            else:
                deleted.phone_verified = 1
            if display_name and display_name != deleted.display_name:
                deleted.display_name = display_name
            db.session.commit()
            account = deleted
            is_new = True
        else:
            if email:
                resolved_name = display_name or email.split('@')[0]
                account = create_account_email(email, resolved_name)
            else:
                resolved_name = display_name or f'Member {phone[-4:]}'
                account = create_account(phone, resolved_name)
            is_new = True
    else:
        if email:
            account.email_verified = 1
        else:
            account.phone_verified = 1
        db.session.commit()

    tokens = issue_tokens(account)
    payload = {**account.to_dict(), **tokens, 'is_new_account': is_new}

    if is_new and account.email:
        try:
            from backend.shared.email.service import send_welcome_email
            send_welcome_email(account.email, account.display_name, account.handle)
        except Exception:
            pass

    return success_response('Verification successful.', payload)


@identity_bp.route('/login', methods=['POST'])
def login():
    """Login via OTP (primary) or password (fallback). Accepts email or phone."""
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    phone = (data.get('phone') or '').strip()
    code = (data.get('code') or '').strip()
    password = (data.get('password') or '').strip()

    identifier = email or phone
    if not identifier:
        return error_response('Email or phone number is required.')

    if email:
        account = Account.query.filter_by(email=email).filter(
            Account.deleted_at.is_(None)
        ).first()
    else:
        account = Account.query.filter_by(phone=phone).filter(
            Account.deleted_at.is_(None)
        ).first()

    if not account:
        return error_response('No account found.')

    # Suspension check relaxed for now (dev) — suspended accounts can still log in.
    # if account.account_status != 'active':
    #     return error_response('Your account has been suspended.')

    if code:
        ok, msg = verify_otp(identifier, code, purpose='login')
        if not ok:
            return error_response(msg)
    elif password:
        if not account.check_password(password):
            # 401 (auth failure) is the correct status — not 400 (bad request).
            return error_response('Incorrect email or password.', status_code=401)
    else:
        create_otp(identifier, purpose='login')
        if email:
            try:
                from backend.shared.email.service import send_otp_email
                send_otp_email(email, account.display_name,
                               __import__('backend.domains.identity.service',
                                          fromlist=['DEV_OTP']).DEV_OTP, 'login')
            except Exception:
                pass
        return success_response('OTP sent.', {
            'requires_otp': True,
            'email': email or None,
            'phone': phone or None,
        })

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


@identity_bp.route('/kyc/advance', methods=['POST'])
@lu_jwt_required
def kyc_advance(account):
    """
    Advance KYC level.
    L0 → L1: phone verified (already done on registration)
    L1 → L2: submit national ID number
    L2 → L3: admin/automated verification (placeholder)
    """
    current_level = account.kyc_level or 0
    data = request.get_json(silent=True) or {}

    if current_level == 0:
        if account.phone_verified:
            account.kyc_level = 1
            db.session.commit()
            if account.email:
                try:
                    from backend.shared.email.service import send_kyc_email
                    send_kyc_email(account.email, account.display_name, 1)
                except Exception:
                    pass
            return success_response('KYC Level 1 unlocked — phone verified.', account.to_dict())
        return error_response('Phone not yet verified. Verify your phone first.')

    if current_level == 1:
        # L1 → L2: submit national ID
        national_id = (data.get('national_id') or '').strip()
        if not national_id:
            return error_response('national_id is required to advance to Level 2.')
        if len(national_id) < 6:
            return error_response('Invalid national ID format.')
        # Store in verifications table (placeholder)
        from datetime import datetime
        from backend.models import db as _db
        _db.session.execute(
            _db.text(
                "INSERT IGNORE INTO lu_verifications (id, account_id, type, status, metadata, created_at) "
                "VALUES (:id, :aid, 'national_id', 'pending', :meta, :now)"
            ),
            {'id': str(__import__('uuid').uuid4()), 'aid': account.id,
             'meta': f'{{"national_id":"{national_id}"}}',
             'now': datetime.utcnow()}
        )
        account.kyc_level = 2
        db.session.commit()
        if account.email:
            try:
                from backend.shared.email.service import send_kyc_email
                send_kyc_email(account.email, account.display_name, 2)
            except Exception:
                pass
        return success_response('KYC Level 2 submitted — National ID under review.', account.to_dict())

    if current_level == 2:
        # L2 → L3: placeholder (requires admin/NIRA integration)
        return error_response('Level 3 verification requires identity verification via NIRA. Contact support.')

    return error_response(f'Already at maximum KYC level ({current_level}).')


@identity_bp.route('/password/reset/request', methods=['POST'])
def password_reset_request():
    """Request a password reset OTP. Accepts email or phone."""
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    phone = (data.get('phone') or '').strip()
    identifier = email or phone
    if not identifier:
        return error_response('Email or phone number is required.')
    from backend.domains.identity.models import Account
    if email:
        account = Account.query.filter_by(email=email).filter(
            Account.deleted_at.is_(None)
        ).first()
    else:
        account = Account.query.filter_by(phone=phone).filter(
            Account.deleted_at.is_(None)
        ).first()
    # Don't reveal whether an address is registered.
    if not account:
        return success_response('If this address is registered, a reset code will be sent.')
    code = create_otp(identifier, purpose='reset')
    logger.info(f'[PasswordReset] OTP for {identifier}: {code} (dev log)')

    if email:
        # Send synchronously so we report the TRUE delivery result instead of
        # silently claiming success when SMTP rejects/credentials fail.
        delivered = False
        try:
            from backend.shared.email.service import send_otp_email
            delivered = bool(send_otp_email(
                email, account.display_name or email, code, 'reset', sync=True))
        except Exception as exc:
            logger.error(f'[PasswordReset] email send error: {exc}')
        if not delivered:
            return error_response(
                'We could not send the reset email right now. Please try again '
                'in a moment or contact support.', status_code=502)
        return success_response('Reset code sent — check your email inbox (and spam).')

    # Phone path (SMS not wired in dev) — code is logged above.
    return success_response('Reset code sent.')


@identity_bp.route('/password/reset', methods=['POST'])
def password_reset():
    """Verify OTP + set new password. Accepts email or phone."""
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    phone = (data.get('phone') or '').strip()
    identifier = email or phone
    code = (data.get('code') or '').strip()
    new_password = (data.get('new_password') or '').strip()

    if not identifier or not code:
        return error_response('Email (or phone) and code are required.')
    if not new_password or len(new_password) < 4:
        return error_response('Password must be at least 4 characters.')

    success, msg = verify_otp(identifier, code, purpose='reset')
    if not success:
        return error_response(msg)

    from backend.domains.identity.models import Account
    if email:
        account = Account.query.filter_by(email=email).filter(
            Account.deleted_at.is_(None)
        ).first()
    else:
        account = Account.query.filter_by(phone=phone).filter(
            Account.deleted_at.is_(None)
        ).first()
    if not account:
        return error_response('Account not found.')

    account.set_password(new_password)
    db.session.commit()
    return success_response('Password updated. You can now sign in.')


@identity_bp.route('/me', methods=['PUT'])
@lu_jwt_required
def update_me(account):
    """Update account settings: display_name, email, modes_enabled."""
    data = request.get_json(silent=True) or {}

    if 'display_name' in data:
        dn = (data['display_name'] or '').strip()
        if len(dn) < 2:
            return error_response('Display name must be at least 2 characters.')
        account.display_name = dn

    if 'email' in data:
        email = (data['email'] or '').strip().lower()
        if email:
            # Check uniqueness
            from backend.domains.identity.models import Account
            existing = Account.query.filter(
                Account.email == email,
                Account.id != account.id,
                Account.deleted_at.is_(None),
            ).first()
            if existing:
                return error_response('This email is already in use.')
            account.email = email
            account.email_verified = 0  # require re-verification

    if 'modes_enabled' in data:
        modes = data['modes_enabled']
        if isinstance(modes, dict):
            # Must keep at least one mode
            if not modes.get('professional') and not modes.get('sparks'):
                return error_response('At least one mode (professional or sparks) must remain enabled.')
            current = dict(account.modes)  # safe accessor (T-API-041)
            current.update(modes)
            account.modes_enabled = current

    db.session.commit()
    return success_response('Account updated.', account.to_dict())


@identity_bp.route('/password', methods=['POST'])
@lu_jwt_required
def change_password(account):
    """Change account password. Requires current password."""
    data = request.get_json(silent=True) or {}
    current_pw = (data.get('current_password') or '').strip()
    new_pw = (data.get('new_password') or '').strip()

    if not new_pw or len(new_pw) < 4:
        return error_response('New password must be at least 4 characters.')

    # If account has a password, verify current one
    if account.password_hash:
        if not current_pw:
            return error_response('Current password is required.')
        if not account.check_password(current_pw):
            return error_response('Current password is incorrect.')

    account.set_password(new_pw)
    db.session.commit()
    return success_response('Password updated successfully.')


@identity_bp.route('/ice', methods=['GET'])
@lu_jwt_required
def ice_config(account):
    """WebRTC ICE server configuration for calling."""
    import os, socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = '127.0.0.1'

    turn_host = os.environ.get('TURN_HOST') or (request.host or '').split(':')[0] or local_ip
    turn_port = int(os.environ.get('TURN_PORT', '3478'))
    turn_user = os.environ.get('TURN_USER', 'linkup')
    turn_pass = os.environ.get('TURN_PASSWORD', 'linkup2026')

    return success_response('ICE config loaded.', {
        'ice_servers': [
            {
                'urls': [f'turn:{turn_host}:{turn_port}',
                         f'turn:{turn_host}:{turn_port}?transport=tcp'],
                'username': turn_user,
                'credential': turn_pass,
            },
            {'urls': f'stun:{turn_host}:{turn_port}'},
            {'urls': 'stun:stun.l.google.com:19302'},
            {'urls': 'stun:stun1.l.google.com:19302'},
        ],
    })


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
    # Suspension check relaxed for now (dev) — only require the account to exist.
    if not account:
        return error_response('Account not found.', status_code=401)

    access_token = create_access_token(identity=account.id)
    return success_response('Token refreshed.', {
        'access_token': access_token,
        'token_type': 'Bearer',
    })


@identity_bp.route('/location', methods=['POST'])
@lu_jwt_required
def update_location(account):
    """
    Update account's last-known GPS location.
    Mobile sends this periodically for Sparks distance filtering.
    Body: { lat: float, lng: float }
    """
    from datetime import datetime
    data = request.get_json(silent=True) or {}
    lat = data.get('lat')
    lng = data.get('lng')
    if lat is None or lng is None:
        return error_response('lat and lng are required.')
    try:
        lat = float(lat)
        lng = float(lng)
    except (ValueError, TypeError):
        return error_response('lat and lng must be numeric.')
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return error_response('Invalid coordinates.')
    now = datetime.utcnow()
    account.last_lat = lat
    account.last_lng = lng
    account.location_updated_at = now
    account.last_seen_at = now
    db.session.commit()
    return success_response('Location updated.', {
        'lat': lat, 'lng': lng,
        'location_updated_at': now.isoformat(),
    })


@identity_bp.route('/accounts/<account_id>/presence', methods=['GET'])
@lu_jwt_required
def account_presence(account, account_id):
    """
    GET /v1/auth/accounts/:id/presence
    Lightweight presence check — returns is_online + last_seen_at for any account.
    Called every 30 s from the open chat thread screen to keep status fresh.
    """
    target = db.session.get(Account, account_id)
    if not target or target.deleted_at:
        return error_response('Account not found.', 404)
    return success_response('Presence loaded.', {
        'id':           target.id,
        'is_online':    target.is_online(),
        'last_seen_at': target.last_seen_at.isoformat() if target.last_seen_at else None,
    })
