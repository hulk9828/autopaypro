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
    card_token: str = Field(..., min_length=1, description="Stripe card token (tok_xxx) or payment method ID (pm_xxx)")
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


class MakePaymentResponse(BaseModel):
    """Result of a make-payment request."""
    success: bool = Field(..., description="Whether the payment was processed successfully")
    message: str = Field(..., description="Human-readable result message")
    transaction: TransactionItem | None = Field(None, description="Created transaction when success=True")


# --- Transaction History (user) ---
class TransactionHistoryResponse(BaseModel):
    """Paginated transaction history."""
    items: list[TransactionItem] = Field(default_factory=list)
    total: int = Field(..., description="Total count of transactions (for pagination)")
