from pydantic import BaseModel, Field


class UpdateDeviceTokenRequest(BaseModel):
    """Request body for updating device token (customer or admin)."""
    device_token: str = Field(..., min_length=1, description="Device token for push notifications (FCM/APNs)")


class UpdateDeviceTokenResponse(BaseModel):
    """Response after updating device token."""
    success: bool = True
    message: str = "Device token updated"
