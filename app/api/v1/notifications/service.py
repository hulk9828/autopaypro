"""Service for sending push notifications to customers."""
import asyncio
import logging
import uuid
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.firebase_client import is_firebase_available, send_fcm_message
from app.models.customer import Customer
from app.models.payment_notification_log import PaymentNotificationLog

logger = logging.getLogger(__name__)


async def send_notification_to_customers(
    db: AsyncSession,
    title: str,
    body: str,
    customer_ids: list[UUID],
    data: dict | None = None,
) -> tuple[int, int, int]:
    """
    Send a push notification to each customer with a device_token.
    Returns (sent_count, no_device_count, failed_count).
    """
    data_dict = {k: str(v) for k, v in (data or {}).items()}
    notification_type = data_dict.get("type", "admin_notification")
    batch_scope = data_dict.get("scope_key") or f"admin:{uuid.uuid4()}"
    firebase_enabled = is_firebase_available()
    sent_count = 0
    no_device_count = 0
    failed_count = 0

    for customer_id in customer_ids:
        customer = await db.get(Customer, customer_id)
        if not customer:
            failed_count += 1
            continue

        # Persist each notification as unread so APIs can support read/unread state.
        db.add(
            PaymentNotificationLog(
                notification_type=notification_type,
                scope_key=f"{batch_scope}:customer:{customer_id}",
                customer_id=customer_id,
                is_read=False,
            )
        )

        device_token = (customer.device_token or "").strip()
        if not device_token:
            no_device_count += 1
            logger.debug("Customer %s has no device_token, skipping", customer_id)
            continue
        logger.info(f"Sending notification to customer {customer_id} with device_token: {device_token}")

        if not firebase_enabled:
            logger.warning("Firebase not configured; notification stored but push not sent")
            continue

        ok = await asyncio.to_thread(send_fcm_message, device_token, title, body, data_dict)
        if ok:
            sent_count += 1
            logger.info("Notification sent to customer %s", customer_id)
        else:
            failed_count += 1
            logger.warning("FCM send failed for customer %s", customer_id)

    await db.commit()
    return sent_count, no_device_count, failed_count
