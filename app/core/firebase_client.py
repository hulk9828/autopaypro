"""
Firebase Cloud Messaging (FCM) client for push notifications.
Initializes from service account file path or JSON string. Disabled if no credentials configured.
"""
import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_firebase_app = None


def _get_credentials():
    """Load Firebase credentials from FIREBASE_CREDENTIALS_JSON (preferred) or FIREBASE_CREDENTIALS_PATH."""
    json_str = (settings.FIREBASE_CREDENTIALS_JSON or "").strip()
    if json_str:
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning("Firebase credentials JSON invalid: %s", e)
            return None
    path = (settings.FIREBASE_CREDENTIALS_PATH or "").strip()
    if path:
        p = Path(path)
        if p.is_absolute():
            full_path = p
        else:
            from app.core.config import BASE_DIR
            full_path = BASE_DIR / path
        if full_path.exists():
            with open(full_path) as f:
                return json.load(f)
        logger.warning("Firebase credentials path not found: %s", full_path)
        return None
    return None


def _ensure_firebase_app():
    """Initialize Firebase Admin app once if credentials are configured."""
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app
    cred_dict = _get_credentials()
    if not cred_dict:
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials
        cred = credentials.Certificate(cred_dict)
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized")
        return _firebase_app
    except Exception as e:
        logger.exception("Firebase initialization failed: %s", e)
        return None


def is_firebase_available() -> bool:
    """Return True if Firebase is configured and initialized."""
    return _ensure_firebase_app() is not None


def send_fcm_message(
    device_token: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> bool:
    """
    Send a push notification to a single device via FCM.
    Returns True if sent successfully, False otherwise (not configured, invalid token, or error).
    data values are stringified (FCM requires string key-value pairs).
    """
    token = (device_token or "").strip()
    if not token:
        return False
    app = _ensure_firebase_app()
    if not app:
        return False
    try:
        from firebase_admin import messaging
        data_dict = {k: str(v) for k, v in (data or {}).items()}
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data_dict,
            token=token,
        )
        messaging.send(message)
        logger.debug("FCM sent to token %s...", token[:20] if len(token) > 20 else token)
        return True
    except messaging.UnregisteredError:
        logger.warning("FCM: device token no longer valid (unregistered)")
        return False
    except Exception as e:
        logger.exception("FCM send failed: %s", e)
        return False
