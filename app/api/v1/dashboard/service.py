from typing import List, Optional
import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.api.v1.dashboard.schemas import (
    DashboardSummaryStats,
    RecentPayment,
    OverdueAccount,
    UpcomingPayment,
    DashboardResponse
)
from app.models.customer import Customer
from app.models.loan import Loan
from app.models.payment import Payment
from app.models.enums import AccountStatus


class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = logging.getLogger(__name__)

    async def get_dashboard_data(self) -> DashboardResponse:
        """
        Get complete dashboard data including summary stats, recent payments,
        overdue accounts, and upcoming payments.
        """
        # Get summary statistics
        summary_stats = await self.get_summary_stats()
        
        # Get recent payments
        recent_payments = await self.get_recent_payments(limit=10)
        
        # Get overdue accounts
        overdue_accounts = await self.get_overdue_accounts()
        
        # Get upcoming payments
        upcoming_payments = await self.get_upcoming_payments(limit=10)
        
        return DashboardResponse(
            summary_stats=summary_stats,
            recent_payments=recent_payments,
            overdue_accounts=overdue_accounts,
            upcoming_payments=upcoming_payments
        )

    async def get_summary_stats(self) -> DashboardSummaryStats:
        """Calculate summary statistics for the dashboard."""
        today = datetime.utcnow()
        start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_of_last_month = (start_of_month - timedelta(days=1)).replace(day=1)
        
        # Total customers
        total_customers_result = await self.db.execute(
            select(func.count(Customer.id))
        )
        total_customers = total_customers_result.scalar() or 0
        
        # Customers this month
        customers_this_month_result = await self.db.execute(
            select(func.count(Customer.id))
            .where(Customer.created_at >= start_of_month)
        )
        customers_this_month = customers_this_month_result.scalar() or 0
        
        # Customers last month
        customers_last_month_result = await self.db.execute(
            select(func.count(Customer.id))
            .where(
                and_(
                    Customer.created_at >= start_of_last_month,
                    Customer.created_at < start_of_month
                )
            )
        )
        customers_last_month = customers_last_month_result.scalar() or 0
        
        # Calculate growth percentage
        customers_growth = None
        if customers_last_month > 0:
            customers_growth = ((customers_this_month - customers_last_month) / customers_last_month) * 100
        
        # Active loans (loans that haven't reached their end date)
        active_loans_result = await self.db.execute(
            select(func.count(Loan.id))
        )
        active_loans = active_loans_result.scalar() or 0
        
        # Loans created this month
        loans_this_month_result = await self.db.execute(
            select(func.count(Loan.id))
            .where(Loan.created_at >= start_of_month)
        )
        loans_this_month = loans_this_month_result.scalar() or 0
        
        # Loans created last month
        loans_last_month_result = await self.db.execute(
            select(func.count(Loan.id))
            .where(
                and_(
                    Loan.created_at >= start_of_last_month,
                    Loan.created_at < start_of_month
                )
            )
        )
        loans_last_month = loans_last_month_result.scalar() or 0
        
        # Calculate loans growth percentage
        loans_growth = None
        if loans_last_month > 0:
            loans_growth = ((loans_this_month - loans_last_month) / loans_last_month) * 100
        
        # Overdue accounts (loans with missed payments)
        overdue_count = await self._count_overdue_accounts()
        
        # Monthly revenue (sum of payments made this month)
        monthly_revenue_result = await self.db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.payment_date >= start_of_month)
        )
        monthly_revenue = float(monthly_revenue_result.scalar() or 0)
        
        # Revenue last month
        revenue_last_month_result = await self.db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0))
            .where(
                and_(
                    Payment.payment_date >= start_of_last_month,
                    Payment.payment_date < start_of_month
                )
            )
        )
        revenue_last_month = float(revenue_last_month_result.scalar() or 0)
        
        # Calculate revenue growth percentage
        revenue_growth = None
        if revenue_last_month > 0:
            revenue_growth = ((monthly_revenue - revenue_last_month) / revenue_last_month) * 100
        
        return DashboardSummaryStats(
            total_customers=total_customers,
            active_loans=active_loans,
            overdue_accounts=overdue_count,
            monthly_revenue=monthly_revenue,
            customers_growth_percent=round(customers_growth, 2) if customers_growth is not None else None,
            loans_growth_percent=round(loans_growth, 2) if loans_growth is not None else None,
            revenue_growth_percent=round(revenue_growth, 2) if revenue_growth is not None else None
        )

    async def get_recent_payments(self, limit: int = 10) -> List[RecentPayment]:
        """Get recent payments."""
        result = await self.db.execute(
            select(Payment, Customer)
            .join(Customer, Payment.customer_id == Customer.id)
            .order_by(Payment.payment_date.desc())
            .limit(limit)
        )
        
        recent_payments = []
        for payment, customer in result.all():
            customer_name = f"{customer.first_name} {customer.last_name}"
            recent_payments.append(
                RecentPayment(
                    payment_id=payment.id,
                    customer_id=payment.customer_id,
                    customer_name=customer_name,
                    payment_date=payment.payment_date,
                    amount=payment.amount,
                    payment_method=payment.payment_method
                )
            )
        
        return recent_payments

    async def get_overdue_accounts(self) -> List[OverdueAccount]:
        """Get accounts with overdue payments."""
        today = datetime.utcnow()
        
        # Get all active loans
        loans_result = await self.db.execute(
            select(Loan, Customer)
            .join(Customer, Loan.customer_id == Customer.id)
            .where(Customer.account_status == AccountStatus.active.value)
        )
        
        overdue_accounts = []
        
        for loan, customer in loans_result.all():
            # Calculate next payment due date
            next_due_date = await self._get_next_payment_due_date(loan)
            
            if next_due_date and next_due_date < today:
                # Check if payment was made for this due date
                payment_exists = await self.db.execute(
                    select(Payment)
                    .where(
                        and_(
                            Payment.loan_id == loan.id,
                            Payment.due_date == next_due_date
                        )
                    )
                )
                
                if not payment_exists.scalar_one_or_none():
                    # This payment is overdue
                    days_overdue = (today - next_due_date).days
                    customer_name = f"{customer.first_name} {customer.last_name}"
                    
                    overdue_accounts.append(
                        OverdueAccount(
                            customer_id=customer.id,
                            customer_name=customer_name,
                            loan_id=loan.id,
                            due_date=next_due_date,
                            overdue_amount=loan.bi_weekly_payment_amount,
                            days_overdue=days_overdue
                        )
                    )
        
        # Sort by days overdue (most overdue first)
        overdue_accounts.sort(key=lambda x: x.days_overdue, reverse=True)
        
        return overdue_accounts

    async def get_upcoming_payments(self, limit: int = 10) -> List[UpcomingPayment]:
        """Get upcoming payments within the next 30 days."""
        today = datetime.utcnow()
        thirty_days_from_now = today + timedelta(days=30)
        
        # Get all active loans
        loans_result = await self.db.execute(
            select(Loan, Customer)
            .join(Customer, Loan.customer_id == Customer.id)
            .where(Customer.account_status == AccountStatus.active.value)
        )
        
        upcoming_payments = []
        
        for loan, customer in loans_result.all():
            # Calculate next payment due date
            next_due_date = await self._get_next_payment_due_date(loan)
            
            if next_due_date and today <= next_due_date <= thirty_days_from_now:
                # Check if payment was already made
                payment_exists = await self.db.execute(
                    select(Payment)
                    .where(
                        and_(
                            Payment.loan_id == loan.id,
                            Payment.due_date == next_due_date
                        )
                    )
                )
                
                if not payment_exists.scalar_one_or_none():
                    days_until_due = (next_due_date - today).days
                    if days_until_due < 0:
                        continue
                    customer_name = f"{customer.first_name} {customer.last_name}"
                    
                    upcoming_payments.append(
                        UpcomingPayment(
                            customer_id=customer.id,
                            customer_name=customer_name,
                            loan_id=loan.id,
                            due_date=next_due_date,
                            payment_amount=loan.bi_weekly_payment_amount,
                            days_until_due=days_until_due
                        )
                    )
        
        # Sort by due date (earliest first)
        upcoming_payments.sort(key=lambda x: x.due_date)
        
        return upcoming_payments[:limit]

    async def _get_next_payment_due_date(self, loan: Loan) -> Optional[datetime]:
        """Calculate the next payment due date for a loan."""
        # First payment is due 14 days after loan creation
        loan_start = loan.created_at
        first_payment_due = loan_start + timedelta(days=14)
        
        # Get all payments for this loan, ordered by due date
        payments_result = await self.db.execute(
            select(Payment)
            .where(Payment.loan_id == loan.id)
            .order_by(Payment.due_date.desc())
        )
        payments = payments_result.scalars().all()
        
        if not payments:
            # No payments made yet, next due date is first payment
            return first_payment_due
        
        # Get the latest payment's due date
        latest_payment_due = payments[0].due_date
        
        # Next payment is 14 days after the latest payment due date
        next_due = latest_payment_due + timedelta(days=14)
        
        # Check if loan has ended
        loan_end_date = loan_start + timedelta(days=int(loan.loan_term_months * 30.44))
        
        if next_due > loan_end_date:
            return None  # Loan has ended
        
        return next_due

    async def _count_overdue_accounts(self) -> int:
        """Count the number of overdue accounts."""
        overdue_accounts = await self.get_overdue_accounts()
        return len(overdue_accounts)
