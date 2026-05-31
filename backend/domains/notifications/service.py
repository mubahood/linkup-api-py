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
    """Create an in-app notification record."""
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
