"""
Notifications service: create + dispatch (OneSignal + in-app).
"""
import uuid
import logging
import requests
from flask import current_app
from backend.models import db
from backend.domains.notifications.models import Notification

logger = logging.getLogger(__name__)


def create_notification(account_id: str, notif_type: str, title: str, body: str = None,
                        data: dict = None, action_url: str = None) -> Notification:
    """Create an in-app notification record and fire a push if the account has a device token."""
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

    # Fire OneSignal push in background thread (non-blocking) if device tokens exist
    try:
        from backend.domains.identity.models import AccountDevice
        devices = AccountDevice.query.filter_by(account_id=account_id).filter(
            AccountDevice.onesignal_player_id.isnot(None)
        ).all()
        player_ids = [d.onesignal_player_id for d in devices if d.onesignal_player_id]
        if player_ids:
            import threading
            threading.Thread(
                target=push_onesignal,
                args=(player_ids, title, body or ''),
                kwargs={'data': data},
                daemon=True,
            ).start()
    except Exception as e:
        logger.warning(f'[Notification] Push dispatch failed for {account_id}: {e}')

    return notif


def push_onesignal(player_ids: list, title: str, body: str, data: dict = None) -> bool:
    """Send a OneSignal push notification."""
    try:
        app_id = current_app.config.get('ONESIGNAL_APP_ID', '')
        api_key = current_app.config.get('ONESIGNAL_REST_API_KEY', '')
        if not app_id or not api_key:
            logger.warning('[OneSignal] Not configured. Skipping push.')
            return False
        payload = {
            'app_id': app_id,
            'include_player_ids': player_ids,
            'headings': {'en': title},
            'contents': {'en': body},
        }
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
