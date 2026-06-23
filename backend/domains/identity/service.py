"""
Identity service: OTP logic, JWT creation, account creation.
Supports email-primary auth (identifier = email address or phone number).
"""
import hashlib
import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta

import bcrypt
from flask_jwt_extended import create_access_token

from backend.models import db
from backend.domains.identity.models import Account, OtpRequest, RefreshToken

logger = logging.getLogger(__name__)

DEV_OTP = '111111'
OTP_EXPIRY_MINUTES = 10
MAX_OTP_ATTEMPTS = 5


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def generate_handle(display_name: str, identifier: str = '') -> str:
    """Generate a unique @handle from the display name."""
    base = re.sub(r'[^a-z0-9]', '', display_name.lower())
    if len(base) < 3:
        base = 'user'
    base = base[:20]
    handle = base
    counter = 1
    while Account.query.filter_by(handle=handle).first():
        handle = f'{base}{counter}'
        counter += 1
    return handle


def create_otp(identifier: str, purpose: str = 'login') -> str:
    """
    Create and store an OTP keyed on identifier (email or phone).
    Returns the OTP code.
    """
    # Invalidate previous unused OTPs for this identifier+purpose
    OtpRequest.query.filter_by(phone=identifier, purpose=purpose).filter(
        OtpRequest.verified_at.is_(None)
    ).delete()

    code = DEV_OTP
    logger.warning(f'[OTP] DEV MODE — {code} for {identifier} (purpose={purpose})')

    otp = OtpRequest(
        id=str(uuid.uuid4()),
        phone=identifier,   # column stores email or phone
        code_hash=_hash_code(code),
        purpose=purpose,
        expires_at=datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES),
    )
    db.session.add(otp)
    db.session.commit()
    return code


def verify_otp(identifier: str, code: str, purpose: str = 'login') -> tuple[bool, str]:
    """Verify an OTP. Returns (success, message)."""
    otp = OtpRequest.query.filter_by(
        phone=identifier,
        purpose=purpose,
    ).filter(
        OtpRequest.verified_at.is_(None),
        OtpRequest.expires_at > datetime.utcnow(),
    ).order_by(OtpRequest.created_at.desc()).first()

    if not otp:
        return False, 'OTP expired or not found. Please request a new one.'

    if otp.attempts >= MAX_OTP_ATTEMPTS:
        return False, 'Too many failed attempts. Please request a new OTP.'

    otp.attempts += 1

    if otp.code_hash != _hash_code(code):
        db.session.commit()
        return False, 'Invalid OTP code.'

    otp.verified_at = datetime.utcnow()
    db.session.commit()
    return True, 'OTP verified.'


def create_account(phone: str, display_name: str) -> Account:
    """Create a new account with phone as the primary identifier."""
    handle = generate_handle(display_name, phone)
    account = Account(
        id=str(uuid.uuid4()),
        handle=handle,
        display_name=display_name,
        phone=phone,
        phone_verified=1,
        modes_enabled={"professional": True, "sparks": False},
        account_status='active',
    )
    db.session.add(account)
    db.session.commit()
    return account


def create_account_email(email: str, display_name: str) -> Account:
    """Create a new account with email as the primary identifier (no phone required)."""
    handle = generate_handle(display_name, email)
    account = Account(
        id=str(uuid.uuid4()),
        handle=handle,
        display_name=display_name,
        email=email,
        email_verified=1,
        modes_enabled={"professional": True, "sparks": False},
        account_status='active',
    )
    db.session.add(account)
    db.session.commit()
    return account


def issue_tokens(account: Account) -> dict:
    """Issue access + refresh tokens for an account."""
    access_token = create_access_token(identity=account.id)

    raw_refresh = secrets.token_urlsafe(48)
    rt = RefreshToken(
        id=str(uuid.uuid4()),
        account_id=account.id,
        token_hash=_hash_code(raw_refresh),
        expires_at=datetime.utcnow() + timedelta(days=30),
    )
    db.session.add(rt)
    db.session.commit()

    return {
        'access_token': access_token,
        'refresh_token': raw_refresh,
        'token_type': 'Bearer',
    }
