from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SendNotificationRequest(BaseModel):
    """Admin sends a push notification to one or more customers."""
    title: str = Field(..., min_length=1, description="Notification title")
    body: str = Field(..., min_length=1, description="Notification body text")
    customer_ids: list[UUID] = Field(..., min_length=1, description="List of customer IDs to send to")
    data: dict[str, Any] | None = Field(None, description="Optional FCM data payload (values will be stringified)")


class SendNotificationResponse(BaseModel):
    """Result of sending notifications."""
    sent_count: int = Field(..., description="Number of customers who received the notification")
    no_device_count: int = Field(..., description="Number of customers without device_token")
    failed_count: int = Field(..., description="Number of FCM send failures")
