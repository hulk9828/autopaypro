"""
Run payment notification cron in the background (non-blocking).
Started on app startup; cancelled on shutdown.
"""
import asyncio
import logging

from app.core.config import settings
from app.cron.payment_notifications import check_and_send_payment_notifications

logger = logging.getLogger(__name__)


async def run_payment_notification_cron_loop() -> None:
    """Loop: run once after short delay, then every configured interval (hours). Non-blocking."""
    interval_hours = getattr(settings, "CRON_PAYMENT_NOTIFICATION_INTERVAL_HOURS", 1.0)
    interval_seconds = max(60.0, interval_hours * 3600)  # minimum 1 minute
    logger.info("Payment notification cron started (interval=%.2f hours)", interval_hours)
    # Small delay so app is fully up before first run
    await asyncio.sleep(10)
    while True:
        try:
            await check_and_send_payment_notifications()
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            logger.info("Payment notification cron cancelled")
            break
        except Exception as e:
            logger.exception("Payment notification cron loop error: %s", e)
            await asyncio.sleep(interval_seconds)
