"""
Payment notification service: send push notifications and prevent duplicates.
Uses PaymentNotificationLog for duplicate prevention (notification_type + scope_key).
Sends via Firebase Cloud Messaging when configured.
"""
import asyncio
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.firebase_client import is_firebase_available, send_fcm_message
from app.models.customer import Customer
from app.models.payment_notification_log import PaymentNotificationLog

logger = logging.getLogger(__name__)


async def was_notification_sent(
    db: AsyncSession,
    notification_type: str,
    scope_key: str,
) -> bool:
    """Return True if this (notification_type, scope_key) was already sent."""
    result = await db.execute(
        select(PaymentNotificationLog.id).where(
            PaymentNotificationLog.notification_type == notification_type,
            PaymentNotificationLog.scope_key == scope_key,
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def send_payment_notification(
    db: AsyncSession,
    customer_id: UUID,
    notification_type: str,
    scope_key: str,
    title: str,
    body: str,
) -> bool:
    """
    Send a payment notification to the customer (push) and log it to prevent duplicates.
    Returns True if notification was sent (and logged), False if skipped (duplicate or no device token).
    """
    if await was_notification_sent(db, notification_type, scope_key):
        logger.debug("Skipping duplicate notification: type=%s scope_key=%s", notification_type, scope_key)
        return False

    customer = await db.get(Customer, customer_id)
    if not customer:
        logger.warning("Customer %s not found for notification", customer_id)
        return False

    device_token = (customer.device_token or "").strip()
    if device_token:
        if is_firebase_available():
            data = {"type": notification_type, "scope_key": scope_key}
            sent = await asyncio.to_thread(
                send_fcm_message,
                device_token,
                title,
                body,
                data,
            )
            if sent:
                logger.info("Payment notification sent via FCM: type=%s customer_id=%s", notification_type, customer_id)
            else:
                logger.warning("FCM send failed for customer %s (type=%s)", customer_id, notification_type)
        else:
            logger.debug(
                "Firebase not configured; notification logged only: type=%s customer_id=%s",
                notification_type, customer_id,
            )
    else:
        logger.debug("No device_token for customer %s, skipping push", customer_id)

    log_entry = PaymentNotificationLog(
        notification_type=notification_type,
        scope_key=scope_key,
        customer_id=customer_id,
    )
    db.add(log_entry)
    await db.commit()
    return True


def scope_key_for_loan_due(loan_id: UUID, due_date) -> str:
    """Scope key for due_tomorrow / overdue notifications."""
    due_str = due_date.strftime("%Y-%m-%d") if hasattr(due_date, "strftime") else str(due_date)
    return f"loan:{loan_id}:due:{due_str}"


def scope_key_for_payment(payment_id: UUID) -> str:
    """Scope key for payment_received / payment_confirmed."""
    return f"payment:{payment_id}"
