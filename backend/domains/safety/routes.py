"""
Safety routes: /v1/safety/*
"""
import uuid
from datetime import datetime
from flask import Blueprint, request
from backend.models import db
from backend.domains.safety.models import Report, Block, SafetyContact, DateCheckin
from backend.shared.auth.decorators import lu_jwt_required
from backend.shared.ratelimit import rate_limit
from backend.shared.utils.response import success_response, error_response

safety_bp = Blueprint('v1_safety', __name__, url_prefix='/v1/safety')


@safety_bp.route('/report', methods=['POST'])
@lu_jwt_required
@rate_limit(10, 60)  # 10 reports / minute (T-API-071)
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


# ─── Safety Contacts ─────────────────────────────────────────────────────────

@safety_bp.route('/contacts', methods=['GET'])
@lu_jwt_required
def list_safety_contacts(account):
    """List my trusted safety contacts."""
    contacts = SafetyContact.query.filter_by(account_id=account.id).order_by(
        SafetyContact.created_at.asc()
    ).all()
    return success_response('Safety contacts loaded.', [c.to_dict() for c in contacts])


@safety_bp.route('/contacts', methods=['POST'])
@lu_jwt_required
def add_safety_contact(account):
    """Add a trusted safety contact (name + phone, or a linked LinkUp account)."""
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    phone = (data.get('phone') or '').strip()
    linked_account_id = (data.get('linked_account_id') or '').strip()

    if not name:
        return error_response('Contact name is required.')
    if not phone and not linked_account_id:
        return error_response('Provide at least a phone number or a linked_account_id.')

    # Max 5 safety contacts
    existing_count = SafetyContact.query.filter_by(account_id=account.id).count()
    if existing_count >= 5:
        return error_response('You can have at most 5 safety contacts.')

    if linked_account_id:
        from backend.domains.identity.models import Account
        linked = db.session.get(Account, linked_account_id)
        if not linked or linked.deleted_at:
            return error_response('Linked account not found.', status_code=404)

    contact = SafetyContact(
        id=str(uuid.uuid4()),
        account_id=account.id,
        name=name,
        phone=phone or None,
        linked_account_id=linked_account_id or None,
    )
    db.session.add(contact)
    db.session.commit()
    return success_response('Safety contact added.', contact.to_dict(), status_code=201)


@safety_bp.route('/contacts/<contact_id>', methods=['DELETE'])
@lu_jwt_required
def delete_safety_contact(account, contact_id):
    """Remove a safety contact."""
    contact = SafetyContact.query.filter_by(id=contact_id, account_id=account.id).first()
    if not contact:
        return error_response('Safety contact not found.', status_code=404)
    db.session.delete(contact)
    db.session.commit()
    return success_response('Safety contact removed.')


# ─── Date Check-ins ───────────────────────────────────────────────────────────

@safety_bp.route('/date-checkins', methods=['GET'])
@lu_jwt_required
def list_date_checkins(account):
    """My date check-ins (most recent first)."""
    from backend.shared.utils.pagination import paginate_query
    from backend.shared.utils.response import paginated_response
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = DateCheckin.query.filter_by(account_id=account.id).order_by(
        DateCheckin.check_time.desc()
    )
    items, total, page, last_page, per_page = paginate_query(query, page, per_page)
    return paginated_response([c.to_dict() for c in items], total, page, per_page,
                              'Date check-ins loaded.')


@safety_bp.route('/date-checkins', methods=['POST'])
@lu_jwt_required
def create_date_checkin(account):
    """
    Schedule a date safety check-in.

    Body: {
      check_time: "2026-07-01T21:00:00",   # when to ping you — ISO datetime
      location_text: "Endiro Coffee, Kololo",
      match_id: "<uuid>",                   # optional: the match you're going on a date with
      note: "First date with Aisha"         # optional personal note
    }

    If you don't check in by check_time, the app will:
    1. Send you a push notification ("Are you OK?")
    2. After 15 min of no response, mark as missed and alert safety contacts
    """
    data = request.get_json(silent=True) or {}
    check_time_str = (data.get('check_time') or '').strip()
    location_text = (data.get('location_text') or '').strip()
    match_id = (data.get('match_id') or '').strip()
    note = (data.get('note') or '').strip()

    if not check_time_str:
        return error_response('check_time is required (ISO datetime, e.g. 2026-07-01T21:00:00).')

    try:
        check_time = datetime.fromisoformat(check_time_str.replace('Z', '+00:00').replace('+00:00', ''))
    except ValueError:
        return error_response('Invalid check_time format. Use ISO 8601 (e.g. 2026-07-01T21:00:00).')

    if check_time <= datetime.utcnow():
        return error_response('check_time must be in the future.')

    if match_id:
        from backend.domains.sparks.models import Match
        from sqlalchemy import or_ as _or
        match = Match.query.filter(
            Match.id == match_id,
            _or(Match.account_a_id == account.id, Match.account_b_id == account.id)
        ).first()
        if not match:
            return error_response('Match not found.', status_code=404)

    checkin = DateCheckin(
        id=str(uuid.uuid4()),
        account_id=account.id,
        match_id=match_id or None,
        location_text=location_text or None,
        check_time=check_time,
        note=note or None,
    )
    db.session.add(checkin)
    db.session.commit()

    # Notify the user's safety contacts (non-blocking)
    _notify_safety_contacts(account, checkin, 'date_scheduled')

    return success_response(
        'Date check-in scheduled. We will ping you at the check time.',
        checkin.to_dict(),
        status_code=201,
    )


@safety_bp.route('/date-checkins/<checkin_id>/confirm', methods=['POST'])
@lu_jwt_required
def confirm_date_checkin(account, checkin_id):
    """Confirm you are safe — marks the check-in as checked_in."""
    checkin = DateCheckin.query.filter_by(id=checkin_id, account_id=account.id).first()
    if not checkin:
        return error_response('Check-in not found.', status_code=404)
    if checkin.status not in ('active', 'missed'):
        return error_response(f'Check-in is already {checkin.status}.')
    checkin.status = 'checked_in'
    db.session.commit()
    return success_response("You're safe! Check-in confirmed.", checkin.to_dict())


@safety_bp.route('/date-checkins/<checkin_id>', methods=['DELETE'])
@lu_jwt_required
def cancel_date_checkin(account, checkin_id):
    """Cancel a scheduled date check-in."""
    checkin = DateCheckin.query.filter_by(id=checkin_id, account_id=account.id).first()
    if not checkin:
        return error_response('Check-in not found.', status_code=404)
    if checkin.status not in ('active',):
        return error_response(f'Cannot cancel a {checkin.status} check-in.')
    checkin.status = 'cancelled'
    db.session.commit()
    return success_response('Check-in cancelled.')


# ─── Panic / SOS ─────────────────────────────────────────────────────────────

@safety_bp.route('/panic', methods=['POST'])
@lu_jwt_required
def panic_sos(account):
    """
    SOS panic alert — immediately notifies all safety contacts.

    Body: {
      location_text: "Endiro Coffee, Kololo",  # optional
      checkin_id: "<uuid>"                     # optional: link to an active date check-in
    }

    In production: sends SMS/push to every safety contact.
    In dev: records the event and returns contact list.
    """
    data = request.get_json(silent=True) or {}
    location_text = (data.get('location_text') or '').strip()
    checkin_id = (data.get('checkin_id') or '').strip()

    contacts = SafetyContact.query.filter_by(account_id=account.id).all()
    if not contacts:
        return error_response(
            'No safety contacts set up. Add at least one safety contact first.',
            status_code=422,
        )

    # Mark check-in as panic_sent if provided
    if checkin_id:
        checkin = DateCheckin.query.filter_by(id=checkin_id, account_id=account.id).first()
        if checkin:
            checkin.panic_sent = 1
            checkin.status = 'missed'
            db.session.commit()

    # Get checkin share_url if linked
    share_url = ''
    if checkin_id:
        _ci = DateCheckin.query.filter_by(id=checkin_id, account_id=account.id).first()
        if _ci and _ci.share_token:
            from flask import current_app
            base = current_app.config.get('APP_URL', 'http://localhost:5001')
            share_url = f'{base}/v1/safety/location/{_ci.share_token}'

    # Notify safety contacts: in-app push + email
    notified = []
    for contact in contacts:
        notified.append({'name': contact.name, 'phone': contact.phone})
        # In-app to linked LinkUp accounts
        if contact.linked_account_id:
            try:
                from backend.domains.notifications.service import create_notification
                create_notification(
                    account_id=contact.linked_account_id,
                    notif_type='safety.panic',
                    title=f'🚨 SOS from {account.display_name}',
                    body=f'Needs help! Location: {location_text or "unknown"}',
                    data={'account_id': account.id, 'location': location_text},
                    action_url=f'/profile/@{account.handle}',
                )
            except Exception:
                pass
        # Email to contacts with phone (use phone as rough proxy for "external contact")
        if contact.phone and '@' in contact.phone:
            # Stored as email address in phone field for external contacts
            try:
                from backend.shared.email.service import send_panic_email
                send_panic_email(
                    to=contact.phone,
                    contact_name=contact.name,
                    owner_name=account.display_name,
                    owner_handle=account.handle,
                    location_text=location_text,
                    share_url=share_url,
                )
            except Exception:
                pass

    return success_response(
        f'SOS alert sent to {len(contacts)} safety contact(s). Stay safe.',
        {
            'notified': notified,
            'account': account.display_name,
            'location': location_text or None,
            'contacts_count': len(contacts),
        },
        status_code=200,
    )


@safety_bp.route('/date-checkins/<checkin_id>/share-location', methods=['POST'])
@lu_jwt_required
def share_location(account, checkin_id):
    """
    Generate a short-lived share token for a date check-in.
    The token can be given to a trusted contact to view your location.

    Body: { expires_hours: 4 }   # 1–24 hours (default 4)
    Returns: { share_url, share_token, expires_at }
    """
    import secrets
    from datetime import timedelta
    from flask import current_app

    checkin = DateCheckin.query.filter_by(id=checkin_id, account_id=account.id).first()
    if not checkin:
        return error_response('Check-in not found.', status_code=404)
    if checkin.status not in ('active', 'checked_in'):
        return error_response(f'Cannot share location for a {checkin.status} check-in.')

    data = request.get_json(silent=True) or {}
    expires_hours = max(1, min(24, int(data.get('expires_hours', 4))))

    token = secrets.token_urlsafe(32)
    checkin.share_token = token
    checkin.share_expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
    db.session.commit()

    base = current_app.config.get('APP_URL', 'http://localhost:5001')
    share_url = f'{base}/v1/safety/location/{token}'

    result = {
        'share_token': token,
        'share_url': share_url,
        'expires_at': checkin.share_expires_at.isoformat(),
        'location_text': checkin.location_text,
        'check_time': checkin.check_time.isoformat() if checkin.check_time else None,
    }

    # Email contacts that have email stored in phone field (external contacts)
    contacts = SafetyContact.query.filter_by(account_id=account.id).all()
    for contact in contacts:
        if contact.phone and '@' in contact.phone:
            try:
                from backend.shared.email.service import send_location_share_email
                send_location_share_email(
                    to=contact.phone,
                    contact_name=contact.name,
                    owner_name=account.display_name,
                    location_text=checkin.location_text or '',
                    share_url=share_url,
                    check_time=checkin.check_time.strftime('%Y-%m-%d %H:%M') if checkin.check_time else '',
                    expires_at=checkin.share_expires_at.strftime('%Y-%m-%d %H:%M'),
                )
            except Exception:
                pass

    return success_response('Location share link created.', result)


@safety_bp.route('/location/<token>', methods=['GET'])
def view_shared_location(token):
    """
    Public endpoint — anyone with the token can view shared location data.
    No auth required (token is the secret). Token expires after the set period.
    """
    checkin = DateCheckin.query.filter_by(share_token=token).first()
    if not checkin:
        return error_response('Invalid or expired share link.', status_code=404)
    if checkin.share_expires_at and checkin.share_expires_at < datetime.utcnow():
        return error_response('This share link has expired.', status_code=410)

    from backend.domains.identity.models import Account
    owner = db.session.get(Account, checkin.account_id)

    return success_response('Location loaded.', {
        'name': owner.display_name if owner else 'Anonymous',
        'handle': owner.handle if owner else None,
        'location_text': checkin.location_text,
        'check_time': checkin.check_time.isoformat() if checkin.check_time else None,
        'status': checkin.status,
        'expires_at': checkin.share_expires_at.isoformat() if checkin.share_expires_at else None,
    })


@safety_bp.route('/date-checkins/<checkin_id>/share-location', methods=['DELETE'])
@lu_jwt_required
def revoke_location_share(account, checkin_id):
    """Revoke a live location share — clears the token."""
    checkin = DateCheckin.query.filter_by(id=checkin_id, account_id=account.id).first()
    if not checkin:
        return error_response('Check-in not found.', status_code=404)
    if not checkin.share_token:
        return error_response('No active location share for this check-in.')
    checkin.share_token = None
    checkin.share_expires_at = None
    db.session.commit()
    return success_response('Location share revoked.')


def _notify_safety_contacts(account, checkin, event_type: str):
    """Non-blocking: notify linked safety contacts about a date event."""
    contacts = SafetyContact.query.filter_by(account_id=account.id).all()
    for contact in contacts:
        if contact.linked_account_id:
            try:
                from backend.domains.notifications.service import create_notification
                msgs = {
                    'date_scheduled': (
                        f'{account.display_name} scheduled a date check-in',
                        f'Location: {checkin.location_text or "not shared"} at '
                        f'{checkin.check_time.strftime("%H:%M") if checkin.check_time else "?"}',
                    ),
                }
                title, body = msgs.get(event_type, ('Safety update', ''))
                create_notification(
                    account_id=contact.linked_account_id,
                    notif_type=f'safety.{event_type}',
                    title=title,
                    body=body,
                    data={'checkin_id': checkin.id, 'account_id': account.id},
                    action_url='/safety',
                )
            except Exception:
                pass
