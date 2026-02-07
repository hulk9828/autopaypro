from fastapi import APIRouter, Depends, status

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.notifications.schemas import SendNotificationRequest, SendNotificationResponse
from app.api.v1.notifications.service import send_notification_to_customers
from app.core.deps import get_db, get_current_active_admin_user
from app.models.user import User

router = APIRouter()


@router.post(
    "/send",
    response_model=SendNotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Send notification to customers (admin)",
    description="Send a push notification with title, body, and optional data to one or more customers. Admin only.",
    tags=["notifications"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def send_notification(
    data: SendNotificationRequest,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin sends a push notification to customers by ID."""
    sent_count, no_device_count, failed_count = await send_notification_to_customers(
        db,
        title=data.title,
        body=data.body,
        customer_ids=data.customer_ids,
        data=data.data,
    )
    return SendNotificationResponse(
        sent_count=sent_count,
        no_device_count=no_device_count,
        failed_count=failed_count,
    )
