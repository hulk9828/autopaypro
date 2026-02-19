from __future__ import annotations

from datetime import date as date_type, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CalendarPaymentItem(BaseModel):
    """Single payment item for calendar (paid, pending, or overdue)."""
    loan_id: UUID
    customer_id: UUID
    customer_name: str
    due_date: datetime
    amount: float
    emi_amount: float = Field(..., description="EMI amount customer has to pay for this due date")
    vehicle_display: Optional[str] = None  # e.g. "2020 Honda Civic"


class PaidCalendarItem(CalendarPaymentItem):
    """Paid payment: includes payment record info."""
    payment_id: UUID
    payment_date: datetime
    payment_method: str


class PaymentCalendarResponse(BaseModel):
    """Payment calendar for a given date: paid, pending, and overdue.
    Item fields use untyped list to avoid Pydantic 2.5 schema recursion.
    """
    date: date_type = Field(..., description="Calendar date requested")
    paid_count: int = Field(..., description="Number of paid payments")
    paid_items: list = Field(default_factory=list, description="Paid payment items")
    pending_count: int = Field(..., description="Number of pending payments")
    pending_items: list = Field(default_factory=list, description="Pending payment items")
    overdue_count: int = Field(..., description="Number of overdue payments")
    overdue_items: list = Field(default_factory=list, description="Overdue payment items")
