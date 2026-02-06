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


# --- Transaction History (user) ---
class TransactionHistoryResponse(BaseModel):
    """Paginated transaction history."""
    items: list[TransactionItem] = Field(default_factory=list)
    total: int = Field(..., description="Total count of transactions (for pagination)")


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
    """Admin view: list of overdue installments plus totals and average overdue days."""
    items: list[OverdueItem] = Field(default_factory=list, description="Overdue installments (optionally paginated)")
    total_overdue_payments: int = Field(..., description="Total count of overdue installments")
    total_outstanding_amount: float = Field(..., description="Sum of amounts for all overdue installments")
    avg_overdue_days: float = Field(..., description="Average days past due across overdue installments")
