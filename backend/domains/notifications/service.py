"""
Notifications service: create + dispatch (OneSignal + in-app).
"""
from __future__ import annotations  # `str | None` needs this on Python 3.9 (prod)
import uuid
import logging
import requests
from flask import current_app
from backend.models import db
from backend.domains.notifications.models import Notification

logger = logging.getLogger(__name__)

# Professional-mode-only notification types — a LinkUp user's job referral,
# mentorship request, link request, hub invite, or endorsement must never
# reach a dating-only (Abanoonya Pro, Uganda Dating App) account, even though
# all brands share one backend and the actor may be on a different app
# entirely. This is the server-side half of "hide, don't delete" — the
# client already hides these features from dating-only users, but that alone
# can't stop a LinkUp user's action from generating a notification for
# someone else's dating-only account.
_PROFESSIONAL_NOTIF_PREFIXES = ('job.', 'mentorship.', 'hub.')
_PROFESSIONAL_NOTIF_TYPES = {'link.requested', 'link.accepted', 'endorsement.received'}


def _is_professional_notif(notif_type: str) -> bool:
    return notif_type in _PROFESSIONAL_NOTIF_TYPES or notif_type.startswith(_PROFESSIONAL_NOTIF_PREFIXES)


def _is_notif_enabled(account_id: str, notif_type: str) -> bool:
    """Check if the account has this notification type enabled (defaults to True if unset)."""
    try:
        from backend.domains.identity.models import Account
        acct = db.session.get(Account, account_id)
        prefs = acct.notif_prefs if acct else {}  # safe accessor (T-API-041)
        if notif_type in prefs:
            return bool(prefs[notif_type])
    except Exception:
        pass
    return True  # default: all notifications on


def resolve_image_url(url: str | None) -> str | None:
    """A stored photo/avatar may be a full CDN URL (R2) or a bare local path
    (backend/shared/storage/local.py's fallback) — OneSignal needs an
    absolute, publicly fetchable URL either way to actually download and
    display it, so a relative path is resolved against APP_URL the same way
    the mobile client's own _resolveUrl() helper does."""
    if not url:
        return None
    if url.startswith('http://') or url.startswith('https://'):
        return url
    base = current_app.config.get('APP_URL', 'https://abanoonyapro.online').rstrip('/')
    return f"{base}{url if url.startswith('/') else '/' + url}"


def photo_for_account(account_id: str) -> str | None:
    """Best available photo for a rich-push image — the dating profile's
    first photo (what's actually shown on their swipe card) if set, else the
    account's own avatar. Returns the raw stored value (may be a relative
    local path or a full CDN URL) — pass through resolve_image_url() before
    handing it to OneSignal."""
    from backend.domains.profile.models import DatingProfile
    from backend.domains.identity.models import Account
    dp = DatingProfile.query.filter_by(account_id=account_id).first()
    if dp and dp.photos:
        first = dp.photos[0]
        if isinstance(first, dict) and first.get('url'):
            return first['url']
    account = db.session.get(Account, account_id)
    return account.avatar if account else None


def create_notification(account_id: str, notif_type: str, title: str, body: str = None,
                        data: dict = None, action_url: str = None,
                        image_url: str = None) -> Notification:
    """Create an in-app notification record and fire a push if the account has a device token.
    image_url, when given, makes the push a rich notification (big picture +
    large icon) — pass the OTHER party's photo for anything with a real,
    already-mutually-visible subject (a match, a message); leave it unset for
    anything that's deliberately anonymized (an unmatched like, a free-tier
    profile view) so a picture never leaks an identity the product is
    intentionally not revealing yet."""
    # Never let a professional-mode notification (job/mentorship/hub/link/
    # endorsement) reach a dating-only (Abanoonya Pro, Uganda Dating App)
    # account, regardless of which app the actor used to trigger it.
    if _is_professional_notif(notif_type):
        try:
            from backend.domains.identity.models import Account
            from backend.shared.app_brand import DATING_ONLY_APP_IDS
            acct = db.session.get(Account, account_id)
            if acct and acct.app_id in DATING_ONLY_APP_IDS:
                return None
        except Exception:
            pass

    # Respect the account's notification preferences
    if not _is_notif_enabled(account_id, notif_type):
        return None

    notif = Notification(
        id=str(uuid.uuid4()),
        account_id=account_id,
        type=notif_type,
        title=title,
        body=body,
        data=data,
        action_url=action_url,
    )
    db.session.add(notif)
    db.session.commit()

    # Live in-app push to the recipient's personal channel (T-API-048)
    try:
        from backend.sockets.realtime import emit_notification
        emit_notification(account_id, notif.to_dict())
    except Exception:
        pass

    # Fire OneSignal push in background thread (non-blocking). Targeted by the
    # account's own ID (OneSignal external_user_id) — this matches what the
    # Flutter client sets via OneSignal.login(accountId) on every login/cold
    # start, so no separate device-token table is needed. OneSignal simply
    # no-ops if that external ID has no active push subscription.
    try:
        import threading
        # action_url rides along in the push payload (not stored on the in-app
        # Notification row's own `data` — that stays exactly what the caller
        # passed) so the client can route generically off one field for every
        # notification type, instead of a per-type switch that needs updating
        # every time a new notif_type is added.
        push_data = {**(data or {}), 'action_url': action_url} if action_url else data
        # A plain threading.Thread does NOT inherit the Flask app context —
        # current_app inside push_onesignal() would raise "working outside of
        # application context" and get silently swallowed by its own
        # try/except, meaning every push before this fix never even reached
        # OneSignal's API. Capture the real app object now (current_app is
        # only a proxy, invalid off-thread) and push a fresh context inside
        # the thread itself.
        app_obj = current_app._get_current_object()
        resolved_image = resolve_image_url(image_url)

        def _push_with_context():
            with app_obj.app_context():
                push_onesignal([account_id], title, body or '', data=push_data,
                                image_url=resolved_image)

        threading.Thread(target=_push_with_context, daemon=True).start()
    except Exception as e:
        logger.warning(f'[Notification] Push dispatch failed for {account_id}: {e}')

    return notif


def push_onesignal(external_user_ids: list, title: str, body: str, data: dict = None,
                    image_url: str = None) -> bool:
    """Send a OneSignal push notification, targeted by external_user_id (account id).
    image_url (already an absolute URL — see resolve_image_url) makes this a
    rich notification: large_icon/big_picture on Android, chrome_* on web.
    ios_attachments is deliberately not set — that needs a Notification
    Service Extension wired into the iOS build to actually download and
    attach the image, which this app doesn't have yet; sending it without
    that extension would just be ignored, so it's left off rather than
    silently no-op on iOS."""
    try:
        app_id = current_app.config.get('ONESIGNAL_APP_ID', '')
        api_key = current_app.config.get('ONESIGNAL_REST_API_KEY', '')
        if not app_id or not api_key:
            logger.warning('[OneSignal] Not configured. Skipping push.')
            return False
        payload = {
            'app_id': app_id,
            'include_external_user_ids': external_user_ids,
            'headings': {'en': title},
            'contents': {'en': body},
            # small_icon (the persistent status-bar icon) deliberately left
            # unset — that value must be a drawable resource name actually
            # bundled in the Android build (katogo's pattern hardcodes
            # 'logo', a resource specific to that app), and this app doesn't
            # have a confirmed one checked in. OneSignal falls back to its
            # own default rather than failing when it's omitted; set
            # ONESIGNAL_SMALL_ICON below once a real bundled drawable name
            # is confirmed.
        }
        channel_id = current_app.config.get('ONESIGNAL_ANDROID_CHANNEL_ID', '')
        if channel_id:
            payload['android_channel_id'] = channel_id
        if image_url:
            payload['large_icon'] = image_url
            payload['big_picture'] = image_url
            payload['chrome_big_picture'] = image_url
            payload['chrome_web_image'] = image_url
        if data:
            payload['data'] = data
        resp = requests.post(
            'https://onesignal.com/api/v1/notifications',
            headers={'Authorization': f'Basic {api_key}', 'Content-Type': 'application/json'},
            json=payload,
            timeout=10,
        )
        return resp.status_code == 200
    except Exception as e:
        logger.error(f'[OneSignal] Push failed: {e}')
        return False
