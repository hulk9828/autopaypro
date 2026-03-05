import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class PaymentMethod(str, Enum):
    cash = "cash"
    card = "card"
    online = "online"
    check = "check"


class PaymentStatus(str, Enum):
    completed = "completed"
    failed = "failed"


class PaymentMode(str, Enum):
    installment = "installment"  # Fixed due-date payment (legacy)
    manual = "manual"  # Flexible amount (customer or admin)
    checkout = "checkout"  # Public checkout flow


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("loans.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    amount = Column(Float, nullable=False)
    emi_amount = Column(Float, nullable=True)  # Expected EMI due for this due date (from loan at time of payment)
    payment_method = Column(String, nullable=False)
    payment_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    due_date = Column(DateTime, nullable=False)  # The due date this payment was for
    status = Column(String(20), default=PaymentStatus.completed.value, nullable=False)
    payment_mode = Column(String(20), default=PaymentMode.installment.value, nullable=False)
    applied_installments = Column(JSON, nullable=True)  # [{due_date: "ISO", applied_amount: float}] for flexible
    note = Column(String(500), nullable=True)  # Admin note for manual payments
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    loan = relationship("Loan", back_populates="payments")
    customer = relationship("Customer", back_populates="payments")
