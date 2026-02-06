from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.calendar.schemas import (
    CalendarPaymentItem,
    PaidCalendarItem,
    PaymentCalendarResponse,
)
from app.models.customer import Customer
from app.models.loan import Loan
from app.models.payment import Payment
from app.models.vehicle import Vehicle


def _get_bi_weekly_due_dates(loan_created_at: datetime, term_months: float, up_to_date: date) -> list[datetime]:
    """Return list of bi-weekly due datetimes for a loan, up to and including up_to_date."""
    first_due = loan_created_at + timedelta(days=14)
    if first_due.date() > up_to_date:
        return []
    due_dates: list[datetime] = []
    d = first_due
    # term_months * 2 ≈ num bi-weekly payments; cap at ~2x for safety
    max_payments = max(1, int(term_months * 2) + 12)
    for _ in range(max_payments):
        if d.date() > up_to_date:
            break
        due_dates.append(d)
        d += timedelta(days=14)
    return due_dates


class CalendarService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_payment_calendar(self, calendar_date: date) -> PaymentCalendarResponse:
        """
        For the given calendar date, return:
        - paid: payments (due on this date) that have been recorded
        - pending: scheduled due on this date but not yet paid
        - overdue: scheduled due before this date but not yet paid
        """
        target_date = calendar_date

        # --- Paid: Payment records where due_date is on target_date ---
        paid_stmt = (
            select(Payment, Loan, Customer, Vehicle)
            .join(Loan, Payment.loan_id == Loan.id)
            .join(Customer, Loan.customer_id == Customer.id)
            .join(Vehicle, Loan.vehicle_id == Vehicle.id)
            .where(func.date(Payment.due_date) == target_date)
        )
        paid_result = await self.db.execute(paid_stmt)
        paid_rows = paid_result.all()
        paid_items = [
            PaidCalendarItem(
                loan_id=p.loan_id,
                customer_id=p.customer_id,
                customer_name=f"{c.first_name} {c.last_name}",
                due_date=p.due_date,
                amount=p.amount,
                vehicle_display=f"{v.year} {v.make} {v.model}" if v else None,
                payment_id=p.id,
                payment_date=p.payment_date,
                payment_method=p.payment_method,
            )
            for p, loan, c, v in paid_rows
        ]

        # --- Set of (loan_id, due_date as date) that have a payment ---
        all_paid_stmt = select(Payment.loan_id, func.date(Payment.due_date).label("d")).where(
            func.date(Payment.due_date) <= target_date
        )
        paid_pairs_result = await self.db.execute(all_paid_stmt)
        paid_pairs = {(r.loan_id, r.d) for r in paid_pairs_result.all()}

        # --- All loans with customer and vehicle ---
        loans_stmt = (
            select(Loan, Customer, Vehicle)
            .join(Customer, Loan.customer_id == Customer.id)
            .join(Vehicle, Loan.vehicle_id == Vehicle.id)
        )
        loans_result = await self.db.execute(loans_stmt)
        loans_rows = loans_result.all()

        pending_items: list[CalendarPaymentItem] = []
        overdue_items: list[CalendarPaymentItem] = []

        for loan, customer, vehicle in loans_rows:
            customer_name = f"{customer.first_name} {customer.last_name}"
            vehicle_display = f"{vehicle.year} {vehicle.make} {vehicle.model}" if vehicle else None
            due_dates = _get_bi_weekly_due_dates(
                loan.created_at,
                loan.loan_term_months,
                target_date,
            )
            for due_dt in due_dates:
                due_d = due_dt.date()
                key = (loan.id, due_d)
                if key in paid_pairs:
                    continue
                item = CalendarPaymentItem(
                    loan_id=loan.id,
                    customer_id=loan.customer_id,
                    customer_name=customer_name,
                    due_date=due_dt,
                    amount=loan.bi_weekly_payment_amount,
                    vehicle_display=vehicle_display,
                )
                if due_d == target_date:
                    pending_items.append(item)
                elif due_d < target_date:
                    overdue_items.append(item)

        return PaymentCalendarResponse(
            date=target_date,
            paid_count=len(paid_items),
            paid_items=paid_items,
            pending_count=len(pending_items),
            pending_items=pending_items,
            overdue_count=len(overdue_items),
            overdue_items=overdue_items,
        )
