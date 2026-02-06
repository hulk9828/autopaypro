"""
Stripe helpers for customer payments via PaymentIntent (mobile/web).
Requires STRIPE_SECRET_KEY in config.
"""
from uuid import UUID

import stripe

from app.core.config import settings


def _stripe_available() -> bool:
    return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_SECRET_KEY.strip())


def create_payment_intent(
    amount_cents: int,
    currency: str,
    *,
    loan_id: UUID,
    customer_id: UUID,
    due_date_iso: str,
    customer_email: str | None = None,
) -> dict:
    """
    Create a Stripe PaymentIntent for a loan payment.
    Returns { "client_secret": "...", "payment_intent_id": "..." }.
    Metadata: loan_id, customer_id, due_date_iso for confirm/record.
    """
    if not _stripe_available():
        raise ValueError("Stripe is not configured (STRIPE_SECRET_KEY)")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=currency or settings.STRIPE_CURRENCY,
        automatic_payment_methods={"enabled": True},
        metadata={
            "loan_id": str(loan_id),
            "customer_id": str(customer_id),
            "due_date_iso": due_date_iso,
        },
        receipt_email=customer_email or None,
    )
    return {"client_secret": intent.client_secret, "payment_intent_id": intent.id}


def confirm_payment_intent_with_token(payment_intent_id: str, card_token: str):
    """Confirm a PaymentIntent using a Stripe card token (tok_xxx). Returns the confirmed PaymentIntent."""
    if not _stripe_available():
        raise ValueError("Stripe is not configured (STRIPE_SECRET_KEY)")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe.PaymentIntent.confirm(payment_intent_id, payment_method=card_token)
