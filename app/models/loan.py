import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Loan(Base):
    __tablename__ = "loans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False)
    total_purchase_price = Column(Float, nullable=False)
    down_payment = Column(Float, nullable=False)
    amount_financed = Column(Float, nullable=False)
    bi_weekly_payment_amount = Column(Float, nullable=False)
    loan_term_months = Column(Float, nullable=False)
    interest_rate = Column(Float, nullable=False)
    status = Column(String(20), default="active", nullable=False)  # active | closed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="loans")
    vehicle = relationship("Vehicle", back_populates="loans")
    payments = relationship("Payment", back_populates="loan")
