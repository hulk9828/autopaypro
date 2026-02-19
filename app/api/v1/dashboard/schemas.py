from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DashboardSummaryStats(BaseModel):
    """Summary statistics for admin dashboard."""
    total_customers: int
    active_loans: int
    overdue_accounts: int
    monthly_revenue: float
    customers_growth_percent: Optional[float] = None
    loans_growth_percent: Optional[float] = None
    revenue_growth_percent: Optional[float] = None


class RecentPayment(BaseModel):
    """Recent payment information."""
    payment_id: UUID
    customer_id: UUID
    customer_name: str
    payment_date: datetime
    amount: float
    emi_amount: float = Field(..., description="EMI amount customer had to pay for this due date")
    payment_method: str
    status: Optional[str] = None  # completed | failed
    vehicle_display: Optional[str] = None  # e.g. "2024 Honda Civic"

    class Config:
        from_attributes = True


class RecentPaymentsResponse(BaseModel):
    """Response for the recent payments endpoint."""
    recent_payments: List[RecentPayment]


class OverdueAccount(BaseModel):
    """Overdue account information."""
    customer_id: UUID
    customer_name: str
    loan_id: UUID
    due_date: datetime
    overdue_amount: float
    emi_amount: float = Field(..., description="EMI amount customer has to pay for this due date")
    days_overdue: int

    class Config:
        from_attributes = True


class UpcomingPayment(BaseModel):
    """Upcoming payment information."""
    customer_id: UUID
    customer_name: str
    loan_id: UUID
    due_date: datetime
    payment_amount: float
    emi_amount: float = Field(..., description="EMI amount customer has to pay for this due date")
    days_until_due: int

    class Config:
        from_attributes = True


class DashboardResponse(BaseModel):
    """Complete dashboard data response."""
    summary_stats: DashboardSummaryStats
    recent_payments: List[RecentPayment]
    overdue_accounts: List[OverdueAccount]
    upcoming_payments: List[UpcomingPayment]
