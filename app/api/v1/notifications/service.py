"""Service for sending push notifications to customers."""
import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.firebase_client import is_firebase_available, send_fcm_message
from app.models.customer import Customer

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
    if not is_firebase_available():
        logger.warning("Firebase not configured; cannot send notifications")
        return 0, len(customer_ids), 0

    data_dict = {k: str(v) for k, v in (data or {}).items()}
    sent_count = 0
    no_device_count = 0
    failed_count = 0

    for customer_id in customer_ids:
        customer = await db.get(Customer, customer_id)
        if not customer:
            failed_count += 1
            continue
        device_token = (customer.device_token or "").strip()
        if not device_token:
            no_device_count += 1
            logger.debug("Customer %s has no device_token, skipping", customer_id)
            continue
        logger.info(f"Sending notification to customer {customer_id} with device_token: {device_token}")

        ok = await asyncio.to_thread(
            send_fcm_message,
            device_token,
            title,
            body,
            data_dict,
        )
        if ok:
            sent_count += 1
            logger.info("Notification sent to customer %s", customer_id)
        else:
            failed_count += 1
            logger.warning("FCM send failed for customer %s", customer_id)

    return sent_count, no_device_count, failed_count
