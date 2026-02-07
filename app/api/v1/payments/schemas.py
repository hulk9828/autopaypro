from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# --- Transaction (single record) - defined first so MakePaymentResponse can reference it ---
class TransactionItem(BaseModel):
    """Single transaction/payment record for history."""
    id: UUID
    loan_id: UUID
    customer_id: UUID
    customer_name: str | None = None
    vehicle_display: str | None = None
    amount: float
    payment_method: str
    status: str = Field(..., description="completed | failed")
    payment_date: datetime
    due_date: datetime
    created_at: datetime | None = None

    class Config:
        from_attributes = True


# --- Make Payment (card token) ---
class MakePaymentRequest(BaseModel):
    """Request to make a payment using card tokenization. No raw card details."""
    card_token: str = Field(
        ...,
        min_length=1,
        description="Stripe PaymentMethod ID (pm_xxx) or card token (tok_xxx). Do NOT send the PaymentIntent client_secret (pi_xxx_secret_xxx).",
    )
    loan_id: UUID = Field(..., description="Loan to pay")
    payment_type: Literal["next", "due"] = Field(
        ...,
        description="'next' = next scheduled unpaid amount; 'due' = specific due date (requires due_date_iso)",
    )
    due_date_iso: str | None = Field(None, description="Required when payment_type is 'due'. ISO date/datetime for the due date.")

    @model_validator(mode="after")
    def due_date_required_when_due_type(self):
        if self.payment_type == "due" and not (self.due_date_iso and self.due_date_iso.strip()):
            raise ValueError("due_date_iso is required when payment_type is 'due'")
        return self

    @model_validator(mode="after")
    def card_token_not_client_secret(self):
        """Reject PaymentIntent client_secret; backend needs PaymentMethod (pm_xxx) or token (tok_xxx)."""
        if "_secret_" in (self.card_token or ""):
            raise ValueError(
                "card_token must be a PaymentMethod ID (pm_xxx) or card token (tok_xxx), not the PaymentIntent client_secret. "
                "On the client, create a PaymentMethod from card details with Stripe and send its id."
            )
        return self


class MakePaymentResponse(BaseModel):
    """Result of a make-payment request."""
    success: bool = Field(..., description="Whether the payment was processed successfully")
    message: str = Field(..., description="Human-readable result message")
    transaction: TransactionItem | None = Field(None, description="Created transaction when success=True")


# --- Admin: update payment status ---
class UpdatePaymentStatusRequest(BaseModel):
    """Admin updates payment status (e.g. to confirmed/completed)."""
    status: Literal["completed", "failed"] = Field(..., description="Payment status")


# --- Admin: record manual payment ---
class RecordManualPaymentRequest(BaseModel):
    """Admin records a manual payment received from a customer."""
    customer_id: UUID = Field(..., description="Customer who paid")
    loan_id: UUID = Field(..., description="Loan the payment is for")
    due_date_iso: str = Field(..., description="Due date of the installment (ISO date/datetime)")
    amount: float = Field(..., description="Amount the customer paid (negative becomes 0)")
    payment_method: Literal["cash", "card", "online", "check"] = Field(
        ..., description="How the customer paid (cash, check, etc.)"
    )
    note: str | None = Field(None, max_length=500, description="Optional note for this payment")

    @model_validator(mode="after")
    def amount_non_negative(self):
        """Clamp negative amount to zero."""
        if self.amount is not None and self.amount < 0:
            object.__setattr__(self, "amount", 0.0)
        return self


# --- Transaction History (user) ---
class TransactionHistoryResponse(BaseModel):
    """Paginated transaction history."""
    items: list[TransactionItem] = Field(default_factory=list)
    total: int = Field(..., description="Total count of transactions (for pagination)")


# --- Admin: Transaction History with summary ---
class AdminTransactionHistoryResponse(BaseModel):
    """Admin transaction history with list and summary stats for dashboard."""
    items: list[TransactionItem] = Field(default_factory=list)
    total: int = Field(..., description="Total count of transactions (for pagination)")
    total_amount: float = Field(..., description="Sum of all transaction amounts (with same filters)")
    completed_count: int = Field(..., description="Number of transactions with status completed")
    pending_count: int = Field(0, description="Number of transactions pending (0 if not used)")
    failed_count: int = Field(..., description="Number of transactions with status failed")


# --- Admin: Overdue payments ---
class OverdueItem(BaseModel):
    """Single overdue installment (scheduled due date with no completed payment)."""
    loan_id: UUID
    customer_id: UUID
    customer_name: str | None = None
    vehicle_display: str | None = None
    due_date: datetime = Field(..., description="Scheduled due date that was missed")
    amount: float = Field(..., description="Bi-weekly payment amount due")
    days_overdue: int = Field(..., description="Days past due date")


class OverduePaymentsResponse(BaseModel):
    """Overdue Accounts: list of overdue installments, count, total amount, and average overdue days."""
    items: list[OverdueItem] = Field(default_factory=list, description="List of overdue payment installments")
    total_overdue_payments: int = Field(..., description="Overdue payment count")
    total_outstanding_amount: float = Field(..., description="Total overdue amount")
    avg_overdue_days: float = Field(..., description="Average overdue days (avg days past due)")


# --- Admin: Payment Summary (paid, unpaid, overdue, totals, search) ---
class DueEntryItem(BaseModel):
    """Single due entry (paid, unpaid, or overdue)."""
    loan_id: UUID
    customer_id: UUID
    customer_name: str | None = None
    vehicle_display: str | None = None
    due_date: datetime = Field(..., description="Scheduled due date")
    amount: float = Field(..., description="Installment amount")
    payment_date: datetime | None = Field(None, description="When paid (for paid dues)")
    payment_id: UUID | None = Field(None, description="Payment id if paid")
    days_overdue: int | None = Field(None, description="Days past due (for overdue)")
    days_until_due: int | None = Field(None, description="Days until due (for unpaid)")


class PaymentSummaryResponse(BaseModel):
    """Payment summary: paid dues, unpaid dues, overdue payments, totals, and search results."""
    paid_dues: list[DueEntryItem] = Field(default_factory=list, description="Completed payments")
    unpaid_dues: list[DueEntryItem] = Field(default_factory=list, description="Future installments not yet paid")
    overdue_payments: list[DueEntryItem] = Field(default_factory=list, description="Past due installments not paid")
    total_collected_amount: float = Field(..., description="Sum of all completed payments")
    pending_amount: float = Field(..., description="Sum of future unpaid installments")
    overdue_amount: float = Field(..., description="Sum of overdue installments")
    total_payment_left: float = Field(..., description="pending_amount + overdue_amount (total remaining)")


# --- Notifications (payment notification log) ---
NOTIFICATION_TYPE_DISPLAY = {
    "payment_received": ("Payment received", "Your payment has been received."),
    "payment_confirmed": ("Payment confirmed", "Your payment has been confirmed."),
    "due_tomorrow": ("Payment due tomorrow", "A payment is due tomorrow."),
    "overdue": ("Payment overdue", "You have an overdue payment."),
}


class NotificationItem(BaseModel):
    """Single notification record for a customer."""
    id: UUID
    notification_type: str = Field(..., description="payment_received | payment_confirmed | due_tomorrow | overdue")
    title: str = Field(..., description="Display title")
    body: str = Field(..., description="Display body")
    sent_at: datetime = Field(..., description="When the notification was sent")
    customer_id: UUID | None = Field(None, description="Present only in admin list")
    customer_name: str | None = Field(None, description="Present only in admin list")


class NotificationListResponse(BaseModel):
    """Paginated list of notifications."""
    items: list[NotificationItem] = Field(default_factory=list)
    total: int = Field(..., description="Total count for pagination")
