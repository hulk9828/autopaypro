"""Log of sent payment notifications for duplicate prevention and audit."""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class PaymentNotificationLog(Base):
    """
    Tracks sent payment notifications to prevent duplicates.
    scope_key: for due_tomorrow/overdue = "loan:{loan_id}:due:{date}"; for payment_received/confirmed = "payment:{payment_id}"
    """
    __tablename__ = "payment_notification_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_type = Column(String(50), nullable=False)  # due_tomorrow, overdue, payment_received, payment_confirmed
    scope_key = Column(String(255), nullable=False, index=True)  # unique per (type, scope_key)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("notification_type", "scope_key", name="uq_notification_type_scope_key"),)
