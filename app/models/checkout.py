import secrets
import uuid
from datetime import datetime, timedelta

from sqlalchemy import Column, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


# Default expiry: 7 days
CHECKOUT_EXPIRY_DAYS = 7


def generate_checkout_token() -> str:
    """URL-safe token for payment link (e.g. 32 chars)."""
    return secrets.token_urlsafe(32)


class Checkout(Base):
    __tablename__ = "checkouts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(String(64), unique=True, index=True, nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("loans.id"), nullable=False)
    amount = Column(Float, nullable=True)  # None = pay full remaining balance
    status = Column(String(20), default="pending", nullable=False)  # pending | completed | expired
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    customer = relationship("Customer", back_populates="checkouts")
    loan = relationship("Loan", back_populates="checkouts")
