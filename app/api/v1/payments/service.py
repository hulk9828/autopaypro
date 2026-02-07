from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.payments.schemas import (
    DueEntryItem,
    NOTIFICATION_TYPE_DISPLAY,
    NotificationItem,
    OverdueItem,
    TransactionItem,
)
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.notification_service import scope_key_for_payment, send_payment_notification
from app.core.stripe_client import create_payment_intent, confirm_payment_intent_with_token
from app.models.customer import Customer
from app.models.loan import Loan
from app.models.payment import Payment, PaymentStatus
from app.models.payment_notification_log import PaymentNotificationLog
from app.models.vehicle import Vehicle


def _get_bi_weekly_due_dates_range(
    loan_created_at: datetime,
    term_months: float,
    from_date: date,
    to_date: date,
) -> list[datetime]:
    """Return bi-weekly due datetimes for a loan between from_date and to_date (inclusive)."""
    first_due = loan_created_at + timedelta(days=14)
    if first_due.date() > to_date:
        return []
    due_dates: list[datetime] = []
    d = first_due
    max_payments = max(1, int(term_months * 2) + 24)
    for _ in range(max_payments):
        if d.date() > to_date:
            break
        if d.date() >= from_date:
            due_dates.append(d)
        d += timedelta(days=14)
    return due_dates


def _ensure_non_negative_amount(amount: float) -> float:
    """Clamp negative payment amount to zero."""
    return max(0.0, float(amount)) if amount is not None else 0.0


def _parse_due_date_iso(due_date_iso: str) -> datetime:
    """Parse ISO date/datetime string to datetime."""
    s = due_date_iso.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        raise ValueError("Invalid due_date_iso format")


class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_paid_due_dates_for_loan(self, loan_id: UUID) -> set[date]:
        """Set of (due_date as date) already paid for this loan."""
        result = await self.db.execute(
            select(func.date(Payment.due_date).label("d")).where(Payment.loan_id == loan_id)
        )
        return {r.d for r in result.all()}

    async def _get_paid_due_dates_for_loan_completed(self, loan_id: UUID) -> set[date]:
        """Set of (due_date as date) with a completed payment for this loan."""
        result = await self.db.execute(
            select(func.date(Payment.due_date).label("d")).where(
                Payment.loan_id == loan_id,
                Payment.status == PaymentStatus.completed.value,
            )
        )
        return {r.d for r in result.all()}

    async def get_next_unpaid_due(self, loan_id: UUID, customer_id: UUID) -> tuple[datetime, float] | None:
        """
        Get the next unpaid due date and amount for the loan.
        Returns (due_datetime, amount) or None if no unpaid due (e.g. all paid or invalid).
        """
        loan = await self.db.get(Loan, loan_id)
        if not loan or loan.customer_id != customer_id:
            return None
        today = date.today()
        from_date = today
        to_date = today + timedelta(days=365 * 2)
        due_dates = _get_bi_weekly_due_dates_range(
            loan.created_at,
            loan.loan_term_months,
            from_date,
            to_date,
        )
        paid = await self._get_paid_due_dates_for_loan(loan_id)
        for due_dt in due_dates:
            if due_dt.date() not in paid:
                return (due_dt, loan.bi_weekly_payment_amount)
        return None

    async def validate_due_date_for_loan(
        self, loan_id: UUID, customer_id: UUID, due_dt: datetime, only_completed: bool = False
    ) -> tuple[datetime, float] | None:
        """Check that due_dt is a valid unpaid due date for the loan. Returns (due_dt, amount) or None.
        If only_completed=True, only completed payments count as paid (allows manual record for failed-due dates)."""
        loan = await self.db.get(Loan, loan_id)
        if not loan or loan.customer_id != customer_id:
            return None
        due_d = due_dt.date()
        paid = await (
            self._get_paid_due_dates_for_loan_completed(loan_id)
            if only_completed
            else self._get_paid_due_dates_for_loan(loan_id)
        )
        if due_d in paid:
            return None
        # Check due_d is one of the scheduled due dates
        from_date = due_d - timedelta(days=14 * 30)
        to_date = due_d + timedelta(days=14)
        scheduled = _get_bi_weekly_due_dates_range(
            loan.created_at,
            loan.loan_term_months,
            from_date,
            to_date,
        )
        for s in scheduled:
            if s.date() == due_d:
                return (s, loan.bi_weekly_payment_amount)
        return None

    async def make_payment(
        self,
        customer_id: UUID,
        loan_id: UUID,
        card_token: str,
        payment_type: str,
        due_date_iso: str | None = None,
    ) -> dict:
        """
        Process payment via card token for next or due amount.
        Returns dict with success, message, transaction (TransactionItem or None).
        """
        print(f"{customer_id} {loan_id} {card_token} {payment_type} {due_date_iso}")
        if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_SECRET_KEY.strip():
            AppException().raise_400("Stripe is not configured")

        loan = await self.db.get(Loan, loan_id)
        if not loan:
            AppException().raise_404("Loan not found")
        if loan.customer_id != customer_id:
            AppException().raise_403("You can only pay for your own loan")
        customer = await self.db.get(Customer, customer_id)
        if not customer:
            AppException().raise_404("Customer not found")

        due_dt: datetime
        amount: float

        if payment_type == "next":
            next_info = await self.get_next_unpaid_due(loan_id, customer_id)
            if not next_info:
                AppException().raise_400("No next payment due for this loan")
            due_dt, amount = next_info
        else:
            if not due_date_iso or not due_date_iso.strip():
                AppException().raise_400("due_date_iso is required when payment_type is 'due'")
            try:
                due_dt = _parse_due_date_iso(due_date_iso)
            except ValueError as e:
                AppException().raise_400(str(e))
            validated = await self.validate_due_date_for_loan(loan_id, customer_id, due_dt)
            if not validated:
                AppException().raise_400("Invalid or already paid due date for this loan")
            due_dt, amount = validated

        amount_cents = int(round(amount * 100))
        if amount_cents < 50:
            AppException().raise_400("Amount too small for Stripe (minimum $0.50)")

        due_date_iso_str = due_dt.isoformat()

        try:
            result = create_payment_intent(
                amount_cents=amount_cents,
                currency=settings.STRIPE_CURRENCY,
                loan_id=loan_id,
                customer_id=customer_id,
                due_date_iso=due_date_iso_str,
                customer_email=customer.email,
            )
            pi = confirm_payment_intent_with_token(result["payment_intent_id"], card_token)
        except Exception as e:
            err_msg = str(e).strip().lower()
            if "no such paymentmethod" in err_msg or "_secret_" in err_msg:
                AppException().raise_400(
                    "Invalid card_token: send a PaymentMethod ID (pm_xxx) or token (tok_xxx) from the client. "
                    "Do not send the PaymentIntent client_secret (pi_xxx_secret_xxx)."
                )
            AppException().raise_400(f"Payment failed: {e}")

        if pi.status != "succeeded":
            AppException().raise_400(f"Payment not completed (status: {pi.status})")

        amount_received = _ensure_non_negative_amount(
            (pi.get("amount_received") or pi.get("amount") or 0) / 100.0
        )
        payment = await self._record_payment(
            loan_id=loan_id,
            customer_id=customer_id,
            due_date=due_dt,
            amount=amount_received,
            status="completed",
        )

        transaction = None
        if payment:
            vehicle = await self.db.get(Vehicle, loan.vehicle_id)
            vehicle_display = f"{vehicle.year} {vehicle.make} {vehicle.model}" if vehicle else None
            customer_name = f"{customer.first_name} {customer.last_name}"
            transaction = TransactionItem(
                id=payment.id,
                loan_id=payment.loan_id,
                customer_id=payment.customer_id,
                customer_name=customer_name,
                vehicle_display=vehicle_display,
                amount=_ensure_non_negative_amount(payment.amount),
                payment_method=payment.payment_method,
                status=payment.status,
                payment_date=payment.payment_date,
                due_date=payment.due_date,
                created_at=payment.created_at,
            )
            # When customer makes payment: save his notification (push + log) so he can get it via GET my-notifications
            await send_payment_notification(
                self.db,
                customer_id=customer_id,
                notification_type="payment_received",
                scope_key=scope_key_for_payment(payment.id),
                title="Payment received",
                body=f"Your payment of ${_ensure_non_negative_amount(payment.amount):.2f} has been received.",
            )

        return {
            "success": True,
            "message": "Payment completed successfully",
            "transaction": transaction,
        }

    async def _record_payment(
        self,
        loan_id: UUID,
        customer_id: UUID,
        due_date: datetime,
        amount: float,
        status: str = "completed",
    ) -> Payment | None:
        """Create payment record. Idempotent: returns None if already exists for this loan + due date."""
        existing = await self.db.execute(
            select(Payment).where(
                Payment.loan_id == loan_id,
                func.date(Payment.due_date) == due_date.date(),
            )
        )
        if existing.scalars().first():
            return None
        payment = Payment(
            loan_id=loan_id,
            customer_id=customer_id,
            amount=amount,
            payment_method="card",
            payment_date=datetime.utcnow(),
            due_date=due_date,
            status=status,
        )
        self.db.add(payment)
        await self.db.commit()
        await self.db.refresh(payment)
        return payment

    async def _record_manual_payment(
        self,
        loan_id: UUID,
        customer_id: UUID,
        due_date: datetime,
        amount: float,
        payment_method: str,
        note: str | None = None,
    ) -> Payment | None:
        """Create manual payment record. Returns None if duplicate (completed payment already exists for loan + due date)."""
        existing = await self.db.execute(
            select(Payment).where(
                Payment.loan_id == loan_id,
                func.date(Payment.due_date) == due_date.date(),
                Payment.status == PaymentStatus.completed.value,
            )
        )
        if existing.scalars().first():
            return None
        payment = Payment(
            loan_id=loan_id,
            customer_id=customer_id,
            amount=amount,
            payment_method=payment_method,
            payment_date=datetime.utcnow(),
            due_date=due_date,
            status=PaymentStatus.completed.value,
            note=note,
        )
        self.db.add(payment)
        await self.db.commit()
        await self.db.refresh(payment)
        return payment

    async def record_manual_payment_admin(
        self,
        customer_id: UUID,
        loan_id: UUID,
        due_date_iso: str,
        amount: float,
        payment_method: str,
        note: str | None = None,
    ) -> TransactionItem | None:
        """Admin records a manual payment received from a customer. Returns TransactionItem or None if invalid."""
        loan = await self.db.get(Loan, loan_id)
        if not loan:
            return None
        if loan.customer_id != customer_id:
            return None
        try:
            due_dt = _parse_due_date_iso(due_date_iso)
        except ValueError:
            return None
        validated = await self.validate_due_date_for_loan(loan_id, customer_id, due_dt, only_completed=True)
        if not validated:
            return None  # Invalid or already paid due date
        amount_safe = _ensure_non_negative_amount(amount)
        payment = await self._record_manual_payment(
            loan_id=loan_id,
            customer_id=customer_id,
            due_date=due_dt,
            amount=amount_safe,
            payment_method=payment_method,
            note=note,
        )
        if not payment:
            return None
        customer = await self.db.get(Customer, customer_id)
        vehicle = await self.db.get(Vehicle, loan.vehicle_id)
        customer_name = f"{customer.first_name} {customer.last_name}" if customer else None
        vehicle_display = f"{vehicle.year} {vehicle.make} {vehicle.model}" if vehicle else None
        await send_payment_notification(
            self.db,
            customer_id=customer_id,
            notification_type="payment_received",
            scope_key=scope_key_for_payment(payment.id),
            title="Payment received",
            body=f"Your payment of ${_ensure_non_negative_amount(payment.amount):.2f} has been received.",
        )
        return TransactionItem(
            id=payment.id,
            loan_id=payment.loan_id,
            customer_id=payment.customer_id,
            customer_name=customer_name,
            vehicle_display=vehicle_display,
            amount=_ensure_non_negative_amount(payment.amount),
            payment_method=payment.payment_method,
            status=payment.status,
            payment_date=payment.payment_date,
            due_date=payment.due_date,
            created_at=payment.created_at,
        )

    async def list_my_transactions(
        self,
        customer_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[TransactionItem], int]:
        """Transaction history for the logged-in user. Returns (items, total)."""
        base = (
            select(Payment, Customer, Vehicle)
            .join(Loan, Payment.loan_id == Loan.id)
            .join(Customer, Payment.customer_id == Customer.id)
            .join(Vehicle, Loan.vehicle_id == Vehicle.id)
            .where(Payment.customer_id == customer_id)
            .order_by(Payment.payment_date.desc())
        )
        total_result = await self.db.execute(
            select(func.count(Payment.id)).where(Payment.customer_id == customer_id)
        )
        total = total_result.scalar_one() or 0
        result = await self.db.execute(base.offset(skip).limit(limit))
        items = []
        for p, c, v in result.all():
            items.append(
                TransactionItem(
                    id=p.id,
                    loan_id=p.loan_id,
                    customer_id=p.customer_id,
                    customer_name=f"{c.first_name} {c.last_name}",
                    vehicle_display=f"{v.year} {v.make} {v.model}" if v else None,
                    amount=_ensure_non_negative_amount(p.amount),
                    payment_method=p.payment_method,
                    status=p.status,
                    payment_date=p.payment_date,
                    due_date=p.due_date,
                    created_at=p.created_at,
                )
            )
        return items, total

    async def list_transactions_admin(
        self,
        customer_id: UUID | None = None,
        loan_id: UUID | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[TransactionItem], int, float, int, int]:
        """Transaction history for all users with filters. Returns (items, total, total_amount, completed_count, failed_count)."""
        base = (
            select(Payment, Customer, Vehicle)
            .join(Loan, Payment.loan_id == Loan.id)
            .join(Customer, Payment.customer_id == Customer.id)
            .join(Vehicle, Loan.vehicle_id == Vehicle.id)
            .order_by(Payment.payment_date.desc())
        )
        count_q = select(func.count(Payment.id))
        sum_q = select(
            func.coalesce(
                func.sum(case((Payment.amount < 0, 0), else_=Payment.amount)), 0
            )
        )
        completed_q = select(func.count(Payment.id)).where(Payment.status == PaymentStatus.completed.value)
        failed_q = select(func.count(Payment.id)).where(Payment.status == "failed")
        if customer_id is not None:
            base = base.where(Payment.customer_id == customer_id)
            count_q = count_q.where(Payment.customer_id == customer_id)
            sum_q = sum_q.where(Payment.customer_id == customer_id)
            completed_q = completed_q.where(Payment.customer_id == customer_id)
            failed_q = failed_q.where(Payment.customer_id == customer_id)
        if loan_id is not None:
            base = base.where(Payment.loan_id == loan_id)
            count_q = count_q.where(Payment.loan_id == loan_id)
            sum_q = sum_q.where(Payment.loan_id == loan_id)
            completed_q = completed_q.where(Payment.loan_id == loan_id)
            failed_q = failed_q.where(Payment.loan_id == loan_id)
        if from_date is not None:
            base = base.where(func.date(Payment.payment_date) >= from_date)
            count_q = count_q.where(func.date(Payment.payment_date) >= from_date)
            sum_q = sum_q.where(func.date(Payment.payment_date) >= from_date)
            completed_q = completed_q.where(func.date(Payment.payment_date) >= from_date)
            failed_q = failed_q.where(func.date(Payment.payment_date) >= from_date)
        if to_date is not None:
            base = base.where(func.date(Payment.payment_date) <= to_date)
            count_q = count_q.where(func.date(Payment.payment_date) <= to_date)
            sum_q = sum_q.where(func.date(Payment.payment_date) <= to_date)
            completed_q = completed_q.where(func.date(Payment.payment_date) <= to_date)
            failed_q = failed_q.where(func.date(Payment.payment_date) <= to_date)

        total_result = await self.db.execute(count_q)
        total = total_result.scalar_one() or 0
        sum_result = await self.db.execute(sum_q)
        total_amount = float(sum_result.scalar_one() or 0)
        completed_result = await self.db.execute(completed_q)
        completed_count = completed_result.scalar_one() or 0
        failed_result = await self.db.execute(failed_q)
        failed_count = failed_result.scalar_one() or 0

        result = await self.db.execute(base.offset(skip).limit(limit))
        items = []
        for p, c, v in result.all():
            items.append(
                TransactionItem(
                    id=p.id,
                    loan_id=p.loan_id,
                    customer_id=p.customer_id,
                    customer_name=f"{c.first_name} {c.last_name}",
                    vehicle_display=f"{v.year} {v.make} {v.model}" if v else None,
                    amount=_ensure_non_negative_amount(p.amount),
                    payment_method=p.payment_method,
                    status=p.status,
                    payment_date=p.payment_date,
                    due_date=p.due_date,
                    created_at=p.created_at,
                )
            )
        return items, total, total_amount, completed_count, failed_count

    async def get_payment_summary_admin(
        self,
        customer_id: UUID | None = None,
        loan_id: UUID | None = None,
        search: str | None = None,
    ) -> dict:
        """
        Get payment summary: paid dues, unpaid dues, overdue payments, totals.
        search: filter by customer name, email, or phone (case-insensitive substring).
        """
        today = date.today()
        base_loans = (
            select(Loan, Customer, Vehicle)
            .join(Customer, Loan.customer_id == Customer.id)
            .join(Vehicle, Loan.vehicle_id == Vehicle.id)
        )
        if customer_id is not None:
            base_loans = base_loans.where(Loan.customer_id == customer_id)
        if loan_id is not None:
            base_loans = base_loans.where(Loan.id == loan_id)
        if search and search.strip():
            q = search.strip()
            base_loans = base_loans.where(
                or_(
                    Customer.first_name.ilike(f"%{q}%"),
                    Customer.last_name.ilike(f"%{q}%"),
                    Customer.email.ilike(f"%{q}%"),
                    Customer.phone.ilike(f"%{q}%"),
                    func.concat(Customer.first_name, " ", Customer.last_name).ilike(f"%{q}%"),
                )
            )
        loans_result = await self.db.execute(base_loans)
        paid_dues: list[DueEntryItem] = []
        unpaid_dues: list[DueEntryItem] = []
        overdue_payments: list[DueEntryItem] = []
        total_collected = 0.0
        pending_amount = 0.0
        overdue_amount = 0.0

        for loan, customer, vehicle in loans_result.all():
            customer_name = f"{customer.first_name} {customer.last_name}" if customer else None
            vehicle_display = f"{vehicle.year} {vehicle.make} {vehicle.model}" if vehicle else None

            # Paid dues: completed payments for this loan
            paid_result = await self.db.execute(
                select(Payment)
                .where(
                    Payment.loan_id == loan.id,
                    Payment.status == PaymentStatus.completed.value,
                )
                .order_by(Payment.due_date.asc())
            )
            for p in paid_result.scalars().all():
                amt = _ensure_non_negative_amount(p.amount)
                total_collected += amt
                paid_dues.append(
                    DueEntryItem(
                        loan_id=loan.id,
                        customer_id=loan.customer_id,
                        customer_name=customer_name,
                        vehicle_display=vehicle_display,
                        due_date=p.due_date,
                        amount=amt,
                        payment_date=p.payment_date,
                        payment_id=p.id,
                        days_overdue=None,
                        days_until_due=None,
                    )
                )

            # Scheduled due dates for this loan
            loan_start = (loan.created_at + timedelta(days=14)).date()
            loan_end = loan.created_at + timedelta(days=int(loan.loan_term_months * 30.44))
            to_date = loan_end.date() if loan_end else today + timedelta(days=365 * 2)
            all_due_dates = _get_bi_weekly_due_dates_range(
                loan.created_at,
                loan.loan_term_months,
                loan_start,
                to_date,
            )
            paid_completed = await self._get_paid_due_dates_for_loan_completed(loan.id)

            for due_dt in all_due_dates:
                due_d = due_dt.date()
                if due_d in paid_completed:
                    continue
                amount = _ensure_non_negative_amount(loan.bi_weekly_payment_amount)
                if due_d < today:
                    days_overdue = (today - due_d).days
                    overdue_amount += amount
                    overdue_payments.append(
                        DueEntryItem(
                            loan_id=loan.id,
                            customer_id=loan.customer_id,
                            customer_name=customer_name,
                            vehicle_display=vehicle_display,
                            due_date=due_dt,
                            amount=amount,
                            payment_date=None,
                            payment_id=None,
                            days_overdue=days_overdue,
                            days_until_due=None,
                        )
                    )
                else:
                    days_until_due = (due_d - today).days
                    pending_amount += amount
                    unpaid_dues.append(
                        DueEntryItem(
                            loan_id=loan.id,
                            customer_id=loan.customer_id,
                            customer_name=customer_name,
                            vehicle_display=vehicle_display,
                            due_date=due_dt,
                            amount=amount,
                            payment_date=None,
                            payment_id=None,
                            days_overdue=None,
                            days_until_due=days_until_due,
                        )
                    )

        overdue_payments.sort(key=lambda x: (x.due_date, x.loan_id))
        unpaid_dues.sort(key=lambda x: (x.due_date, x.loan_id))
        paid_dues.sort(key=lambda x: (x.due_date, x.loan_id))

        return {
            "paid_dues": paid_dues,
            "unpaid_dues": unpaid_dues,
            "overdue_payments": overdue_payments,
            "total_collected_amount": total_collected,
            "pending_amount": pending_amount,
            "overdue_amount": overdue_amount,
            "total_payment_left": pending_amount + overdue_amount,
        }

    async def list_overdue_for_admin(
        self,
        skip: int = 0,
        limit: int = 500,
    ) -> tuple[list[OverdueItem], int, float, float]:
        """
        List overdue installments (scheduled due dates in the past with no completed payment).
        Returns (items_page, total_overdue_count, total_outstanding_amount, avg_overdue_days).
        """
        today = date.today()
        loans_result = await self.db.execute(
            select(Loan, Customer, Vehicle)
            .join(Customer, Loan.customer_id == Customer.id)
            .join(Vehicle, Loan.vehicle_id == Vehicle.id)
        )
        all_items: list[OverdueItem] = []
        for loan, customer, vehicle in loans_result.all():
            # Due dates from loan start up to (and including) yesterday
            from_date = (loan.created_at + timedelta(days=14)).date()
            to_date = today
            due_dates = _get_bi_weekly_due_dates_range(
                loan.created_at,
                loan.loan_term_months,
                from_date,
                to_date,
            )
            paid_completed = await self._get_paid_due_dates_for_loan_completed(loan.id)
            customer_name = f"{customer.first_name} {customer.last_name}" if customer else None
            vehicle_display = f"{vehicle.year} {vehicle.make} {vehicle.model}" if vehicle else None
            for due_dt in due_dates:
                due_d = due_dt.date()
                if due_d >= today or due_d in paid_completed:
                    continue
                days_overdue = (today - due_d).days
                all_items.append(
                    OverdueItem(
                        loan_id=loan.id,
                        customer_id=loan.customer_id,
                        customer_name=customer_name,
                        vehicle_display=vehicle_display,
                        due_date=due_dt,
                        amount=_ensure_non_negative_amount(loan.bi_weekly_payment_amount),
                        days_overdue=days_overdue,
                    )
                )
        # Sort by due_date ascending (oldest overdue first) or by days_overdue desc
        all_items.sort(key=lambda x: (x.due_date, x.loan_id))
        total_count = len(all_items)
        total_outstanding = sum(i.amount for i in all_items)
        avg_days = (sum(i.days_overdue for i in all_items) / total_count) if total_count else 0.0
        page = all_items[skip : skip + limit]
        return (page, total_count, total_outstanding, avg_days)

    async def update_payment_status_admin(
        self,
        payment_id: UUID,
        status: str,
    ) -> TransactionItem | None:
        """Admin updates payment status. Sends 'payment_confirmed' notification when status is completed."""
        payment = await self.db.get(Payment, payment_id)
        if not payment:
            return None
        payment.status = status
        self.db.add(payment)
        await self.db.commit()
        await self.db.refresh(payment)
        if status == "completed":
            await send_payment_notification(
                self.db,
                customer_id=payment.customer_id,
                notification_type="payment_confirmed",
                scope_key=scope_key_for_payment(payment.id),
                title="Payment confirmed",
                body=f"Your payment of ${_ensure_non_negative_amount(payment.amount):.2f} has been confirmed.",
            )
        loan = await self.db.get(Loan, payment.loan_id)
        customer = await self.db.get(Customer, payment.customer_id)
        vehicle = await self.db.get(Vehicle, loan.vehicle_id) if loan else None
        vehicle_display = f"{vehicle.year} {vehicle.make} {vehicle.model}" if vehicle else None
        customer_name = f"{customer.first_name} {customer.last_name}" if customer else None
        return TransactionItem(
            id=payment.id,
            loan_id=payment.loan_id,
            customer_id=payment.customer_id,
            customer_name=customer_name,
            vehicle_display=vehicle_display,
            amount=_ensure_non_negative_amount(payment.amount),
            payment_method=payment.payment_method,
            status=payment.status,
            payment_date=payment.payment_date,
            due_date=payment.due_date,
            created_at=payment.created_at,
        )

    def _notification_display(self, notification_type: str) -> tuple[str, str]:
        """Return (title, body) for a notification type."""
        return NOTIFICATION_TYPE_DISPLAY.get(
            notification_type,
            (notification_type.replace("_", " ").title(), "Notification sent."),
        )

    async def list_notifications_for_customer(
        self,
        customer_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[NotificationItem], int]:
        """List payment notifications for a customer. Returns (items, total)."""
        base = (
            select(PaymentNotificationLog)
            .where(PaymentNotificationLog.customer_id == customer_id)
            .order_by(PaymentNotificationLog.sent_at.desc())
        )
        total_result = await self.db.execute(
            select(func.count(PaymentNotificationLog.id)).where(
                PaymentNotificationLog.customer_id == customer_id
            )
        )
        total = total_result.scalar_one() or 0
        result = await self.db.execute(base.offset(skip).limit(limit))
        items = []
        for log in result.scalars().all():
            title, body = self._notification_display(log.notification_type)
            items.append(
                NotificationItem(
                    id=log.id,
                    notification_type=log.notification_type,
                    title=title,
                    body=body,
                    sent_at=log.sent_at,
                    customer_id=None,
                    customer_name=None,
                )
            )
        return items, total

    async def list_notifications_admin(
        self,
        customer_id: UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[NotificationItem], int]:
        """List payment notifications for admin (all or filtered by customer_id). Returns (items, total)."""
        base = (
            select(PaymentNotificationLog, Customer)
            .join(Customer, PaymentNotificationLog.customer_id == Customer.id)
            .order_by(PaymentNotificationLog.sent_at.desc())
        )
        count_q = select(func.count(PaymentNotificationLog.id))
        if customer_id is not None:
            base = base.where(PaymentNotificationLog.customer_id == customer_id)
            count_q = count_q.where(PaymentNotificationLog.customer_id == customer_id)
        total_result = await self.db.execute(count_q)
        total = total_result.scalar_one() or 0
        result = await self.db.execute(base.offset(skip).limit(limit))
        items = []
        for log, customer in result.all():
            title, body = self._notification_display(log.notification_type)
            customer_name = f"{customer.first_name} {customer.last_name}" if customer else None
            items.append(
                NotificationItem(
                    id=log.id,
                    notification_type=log.notification_type,
                    title=title,
                    body=body,
                    sent_at=log.sent_at,
                    customer_id=log.customer_id,
                    customer_name=customer_name,
                )
            )
        return items, total
