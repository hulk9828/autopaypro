"""
Cron job: check and send payment notifications for due tomorrow and overdue.
Runs on a schedule (configurable interval). Does NOT handle payment_received or payment_confirmed.
"""
import logging
from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_async_session_maker_instance
from app.core.loan_schedule import get_bi_weekly_due_dates_range
from app.core.utils import ensure_non_negative_amount
from app.core.notification_service import (
    scope_key_for_loan_due,
    send_payment_notification,
)
from app.models.loan import Loan
from app.models.payment import Payment

logger = logging.getLogger(__name__)


async def _get_paid_due_dates_for_loan(session: AsyncSession, loan_id: UUID) -> set[date]:
    """Set of due dates (as date) already paid for this loan."""
    result = await session.execute(
        select(func.date(Payment.due_date).label("d")).where(Payment.loan_id == loan_id)
    )
    return {r.d for r in result.all()}


async def check_and_send_payment_notifications() -> None:
    """
    Query payments due tomorrow and overdue by X days; send notifications and log.
    Prevents duplicates via PaymentNotificationLog (notification_type + scope_key).
    """
    logger.info("Cron: checkAndSendPaymentNotifications started")
    session_maker = get_async_session_maker_instance()
    try:
        async with session_maker() as session:
            today = date.today()
            tomorrow = today + timedelta(days=1)
            overdue_days = getattr(settings, "OVERDUE_DAYS_FOR_NOTIFICATION", 7)
            overdue_from = today - timedelta(days=overdue_days)

            result = await session.execute(
                select(Loan).where(Loan.id.isnot(None))
            )
            loans = result.scalars().all()
            sent_due_tomorrow = 0
            sent_overdue = 0
            errors = 0

            for loan in loans:
                try:
                    paid = await _get_paid_due_dates_for_loan(session, loan.id)
                    customer_id = loan.customer_id

                    # Due tomorrow
                    due_tomorrow_dates = get_bi_weekly_due_dates_range(
                        loan.created_at,
                        loan.loan_term_months,
                        tomorrow,
                        tomorrow,
                    )
                    for due_dt in due_tomorrow_dates:
                        if due_dt.date() in paid:
                            continue
                        scope_key = scope_key_for_loan_due(loan.id, due_dt.date())
                        ok = await send_payment_notification(
                            session,
                            customer_id=customer_id,
                            notification_type="due_tomorrow",
                            scope_key=scope_key,
                            title="Payment due tomorrow",
                            body=f"Your payment of ${ensure_non_negative_amount(loan.bi_weekly_payment_amount):.2f} is due tomorrow.",
                        )
                        if ok:
                            sent_due_tomorrow += 1

                    # Overdue (past due, within last OVERDUE_DAYS_FOR_NOTIFICATION days)
                    overdue_dates = get_bi_weekly_due_dates_range(
                        loan.created_at,
                        loan.loan_term_months,
                        overdue_from,
                        today - timedelta(days=1),
                    )
                    for due_dt in overdue_dates:
                        if due_dt.date() in paid:
                            continue
                        scope_key = scope_key_for_loan_due(loan.id, due_dt.date())
                        ok = await send_payment_notification(
                            session,
                            customer_id=customer_id,
                            notification_type="overdue",
                            scope_key=scope_key,
                            title="Payment overdue",
                            body=f"Your payment of ${ensure_non_negative_amount(loan.bi_weekly_payment_amount):.2f} was due on {due_dt.date()} and is now overdue.",
                        )
                        if ok:
                            sent_overdue += 1

                except Exception as e:
                    errors += 1
                    logger.exception("Cron: error processing loan %s: %s", loan.id, e)

            logger.info(
                "Cron: checkAndSendPaymentNotifications finished — due_tomorrow=%s overdue=%s errors=%s",
                sent_due_tomorrow, sent_overdue, errors,
            )
    except Exception as e:
        logger.exception("Cron: checkAndSendPaymentNotifications failed: %s", e)
