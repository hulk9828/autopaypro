from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# --- Receipt (payment receipt data for display/print) ---
class PaymentReceiptResponse(BaseModel):
    """Receipt data for a completed payment. Use for display or print."""
    receipt_number: str = Field(..., description="Unique receipt identifier (e.g. RCP-xxx)")
    payment_id: UUID = Field(..., description="Payment ID")
    company_name: str = Field(default="AutoLoanPro", description="Company name for receipt header")
    customer_name: str = Field(..., description="Customer full name")
    customer_email: str | None = Field(None, description="Customer email")
    customer_phone: str | None = Field(None, description="Customer phone")
    amount: float = Field(..., description="Amount paid")
    currency: str = Field(default="usd", description="Currency code")
    payment_method: str = Field(..., description="Payment method (card, cash, etc.)")
    payment_date: datetime = Field(..., description="Date and time of payment")
    due_date: datetime = Field(..., description="Due date this payment was for")
    status: str = Field(..., description="Payment status (e.g. completed)")
    loan_id: UUID = Field(..., description="Loan ID")
    vehicle_display: str | None = Field(None, description="Vehicle (year make model)")
    loan_status: Literal["active", "completed"] = Field(
        default="active",
        description="active = loan open; completed = loan fully paid (closed)",
    )
    note: str | None = Field(None, description="Optional note (e.g. for manual payments)")
    created_at: datetime | None = Field(None, description="Record created at")


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
    loan_status: Literal["active", "completed"] = Field(
        default="active",
        description="active = loan open; completed = loan fully paid (closed)",
    )

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


# --- Public checkout (no auth): get payment details + Stripe client_secret ---
class CheckoutRequest(BaseModel):
    """Request for checkout: identify customer and due; no auth required."""
    loan_id: UUID = Field(..., description="Loan to pay")
    payment_type: Literal["next", "due"] = Field(
        ...,
        description="'next' = next scheduled unpaid; 'due' = specific due date (requires due_date_iso)",
    )
    due_date_iso: str | None = Field(None, description="Required when payment_type is 'due'. ISO date for the due date.")
    email: str | None = Field(None, description="Customer email (use email or customer_id to identify customer)")
    customer_id: UUID | None = Field(None, description="Customer ID (use email or customer_id to identify customer)")

    @model_validator(mode="after")
    def due_date_required_when_due_type(self):
        if self.payment_type == "due" and not (self.due_date_iso and self.due_date_iso.strip()):
            raise ValueError("due_date_iso is required when payment_type is 'due'")
        return self

    @model_validator(mode="after")
    def require_email_or_customer_id(self):
        if not (self.email and self.email.strip()) and not self.customer_id:
            raise ValueError("Provide either email or customer_id to identify the customer")
        return self


class CheckoutResponse(BaseModel):
    """Payment details for checkout: amount, Stripe client_secret, and display info. No auth required."""
    amount: float = Field(..., description="Amount due in currency units")
    amount_cents: int = Field(..., description="Amount in cents for Stripe")
    currency: str = Field(..., description="Currency code (e.g. usd)")
    client_secret: str = Field(..., description="Stripe PaymentIntent client_secret for client-side confirm")
    payment_intent_id: str = Field(..., description="Stripe PaymentIntent ID (pi_xxx)")
    due_date: datetime = Field(..., description="Due date for this installment")
    customer_name: str | None = Field(None, description="Customer display name")
    vehicle_display: str | None = Field(None, description="Vehicle description (year make model)")
    loan_id: UUID = Field(..., description="Loan ID")
    customer_id: UUID = Field(..., description="Customer ID")
    loan_status: Literal["active", "completed"] = Field(
        default="active",
        description="active = loan open; completed = loan fully paid (closed)",
    )


class GetCheckoutResponse(BaseModel):
    """Checkout details retrieved by payment_intent_id (e.g. for polling or status). Includes Stripe status."""
    amount: float = Field(..., description="Amount in currency units")
    amount_cents: int = Field(..., description="Amount in cents")
    currency: str = Field(..., description="Currency code (e.g. usd)")
    status: str = Field(..., description="Stripe PaymentIntent status: requires_payment_method, requires_confirmation, requires_action, processing, succeeded, canceled")
    client_secret: str | None = Field(None, description="Stripe client_secret (for client-side confirm when status is requires_payment_method/requires_confirmation)")
    payment_intent_id: str = Field(..., description="Stripe PaymentIntent ID (pi_xxx)")
    due_date: datetime | None = Field(None, description="Due date from metadata")
    customer_name: str | None = Field(None, description="Customer display name")
    vehicle_display: str | None = Field(None, description="Vehicle description")
    loan_id: UUID | None = Field(None, description="Loan ID from metadata")
    customer_id: UUID | None = Field(None, description="Customer ID from metadata")
    loan_status: Literal["active", "completed"] = Field(
        default="active",
        description="active = loan open; completed = loan fully paid (closed)",
    )


# --- Public payment (no auth): confirm with card_token using payment_intent_id from checkout ---
class PublicPaymentRequest(BaseModel):
    """Confirm payment using PaymentIntent from checkout. No auth required."""
    payment_intent_id: str = Field(..., min_length=1, description="Stripe PaymentIntent ID from checkout response")
    card_token: str = Field(
        ...,
        min_length=1,
        description="Stripe PaymentMethod ID (pm_xxx) or card token (tok_xxx). Not the client_secret.",
    )

    @model_validator(mode="after")
    def card_token_not_client_secret(self):
        if "_secret_" in (self.card_token or ""):
            raise ValueError(
                "card_token must be a PaymentMethod ID (pm_xxx) or card token (tok_xxx), not the PaymentIntent client_secret."
            )
        return self


# --- Admin: update payment status ---
class UpdatePaymentStatusRequest(BaseModel):
    """Admin updates payment status (e.g. to confirmed/completed)."""
    status: Literal["completed", "failed"] = Field(..., description="Payment status")


# --- Admin: bulk overdue reminder (email + notification) ---
class BulkOverdueReminderRequest(BaseModel):
    """Optional overrides for bulk overdue reminder email and notification. All optional."""
    email_subject: str | None = Field(None, max_length=200, description="Custom email subject (default: AutoLoanPro - Overdue Payment Reminder)")
    email_body_override: str | None = Field(None, description="Custom HTML email body (replaces default; no template variables)")
    notification_title: str | None = Field(None, max_length=100, description="Push notification title (default: Overdue Payment Reminder)")
    notification_body: str | None = Field(None, max_length=500, description="Push notification body (default message about overdue payments)")


class BulkOverdueReminderResponse(BaseModel):
    """Result of sending bulk email and notifications to customers with overdue payments."""
    customer_count: int = Field(..., description="Number of distinct customers with overdue payments")
    emails_sent: int = Field(..., description="Emails sent successfully")
    emails_failed: int = Field(..., description="Emails that failed to send")
    notifications_sent: int = Field(..., description="Push notifications delivered")
    no_device_count: int = Field(..., description="Customers with no device token (app not installed / no token)")
    notifications_failed: int = Field(..., description="Push notifications that failed to send")


# --- Admin: waive overdue installment ---
class WaiveOverdueRequest(BaseModel):
    """Admin waives an overdue (or any unpaid) installment for a loan. Creates a zero-amount completed payment marked as waived."""
    loan_id: UUID = Field(..., description="Loan ID")
    due_date_iso: str = Field(..., description="Due date of the installment to waive (ISO date/datetime)")
    note: str | None = Field(None, max_length=500, description="Optional reason or note for the waiver")


class WaiveOverdueByCustomerRequest(BaseModel):
    """Admin waives the earliest overdue installment for a customer's loan. Uses customer_id and loan_id only."""
    customer_id: UUID = Field(..., description="Customer ID")
    loan_id: UUID = Field(..., description="Loan ID (must belong to this customer)")
    note: str | None = Field(None, max_length=500, description="Optional reason or note for the waiver")


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
    loan_status: Literal["active", "completed"] = Field(
        default="active",
        description="active = loan open; completed = loan fully paid (closed)",
    )


class OverduePaymentsResponse(BaseModel):
    """Overdue Accounts: list of overdue installments, count, total amount, and average overdue days."""
    items: list[OverdueItem] = Field(default_factory=list, description="List of overdue payment installments")
    total_overdue_payments: int = Field(..., description="Overdue payment count")
    total_outstanding_amount: float = Field(..., description="Total overdue amount")
    avg_overdue_days: float = Field(..., description="Average overdue days (avg days past due)")


# --- Admin: Customers with dues (for create checkout) ---
class DueCustomerItem(BaseModel):
    """One per (customer, loan) with unpaid dues. Use loan_id + customer_id/email to call create checkout (payment_type=next)."""
    customer_id: UUID = Field(..., description="Customer ID")
    email: str = Field(..., description="Customer email (for create checkout)")
    customer_name: str | None = Field(None, description="Customer full name")
    phone: str | None = Field(None, description="Customer phone")
    loan_id: UUID = Field(..., description="Loan ID (for create checkout)")
    vehicle_display: str | None = Field(None, description="Vehicle (year make model)")
    unpaid_count: int = Field(..., description="Number of unpaid installments")
    total_unpaid_amount: float = Field(..., description="Total amount due for this loan")
    next_due_date: datetime | None = Field(None, description="First unpaid due date")
    next_due_date_iso: str | None = Field(None, description="First unpaid due date ISO (for create checkout with payment_type=due)")
    loan_status: Literal["active", "completed"] = Field(
        default="active",
        description="active = loan open; completed = loan fully paid (closed)",
    )


class DueCustomersResponse(BaseModel):
    """List of customers who have unpaid dues, with loan_id and details for create checkout."""
    items: list[DueCustomerItem] = Field(default_factory=list)
    total: int = Field(..., description="Total count (for pagination)")


# --- Admin: Due installments list (for create checkout per due) ---
class DueInstallmentItem(BaseModel):
    """Single unpaid installment. Use loan_id, customer_id/email, due_date_iso to call create checkout (payment_type=due)."""
    loan_id: UUID = Field(..., description="Loan ID (for create checkout)")
    customer_id: UUID = Field(..., description="Customer ID (for create checkout)")
    email: str = Field(..., description="Customer email (for create checkout)")
    customer_name: str | None = Field(None, description="Customer full name")
    phone: str | None = Field(None, description="Customer phone")
    vehicle_display: str | None = Field(None, description="Vehicle (year make model)")
    due_date: datetime = Field(..., description="Due date for this installment")
    due_date_iso: str = Field(..., description="Due date ISO (for create checkout payment_type=due, due_date_iso)")
    amount: float = Field(..., description="Amount due")
    days_overdue: int | None = Field(None, description="Days past due (if overdue)")
    days_until_due: int | None = Field(None, description="Days until due (if future)")
    loan_status: Literal["active", "completed"] = Field(
        default="active",
        description="active = loan open; completed = loan fully paid (closed)",
    )


class DueInstallmentsResponse(BaseModel):
    """List of all unpaid due installments with everything needed for create checkout."""
    items: list[DueInstallmentItem] = Field(default_factory=list)
    total: int = Field(..., description="Total count (for pagination)")
    total_amount: float = Field(..., description="Sum of all unpaid amounts in list (or total)")


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
    loan_status: Literal["active", "completed"] = Field(
        default="active",
        description="active = loan open; completed = loan fully paid (closed)",
    )


class PaymentSummaryItem(BaseModel):
    """Single due/payment entry in the combined list with status: paid_dues | unpaid_dues | overdue_payments."""
    payment_status: Literal["paid_dues", "unpaid_dues", "overdue_payments"] = Field(
        ...,
        description="paid_dues = payment done; unpaid_dues = future due; overdue_payments = past due not paid",
    )
    loan_id: UUID
    customer_id: UUID
    customer_name: str | None = None
    vehicle_display: str | None = None
    due_date: datetime = Field(..., description="Scheduled due date")
    amount: float = Field(..., description="Installment amount")
    payment_date: datetime | None = Field(None, description="When paid (for paid_dues)")
    payment_id: UUID | None = Field(None, description="Payment id if paid")
    days_overdue: int | None = Field(None, description="Days past due (for overdue_payments)")
    days_until_due: int | None = Field(None, description="Days until due (for unpaid_dues)")
    loan_status: Literal["active", "completed"] = Field(
        default="active",
        description="active = loan open; completed = loan fully paid (closed)",
    )


class PaymentSummaryResponse(BaseModel):
    """Payment summary: single list of all dues with payment_status enum, plus totals."""
    items: list[PaymentSummaryItem] = Field(
        default_factory=list,
        description="All dues in one list: payment_status = paid_dues | unpaid_dues | overdue_payments",
    )
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
