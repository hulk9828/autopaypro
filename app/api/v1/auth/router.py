from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.schemas import UpdateDeviceTokenRequest, UpdateDeviceTokenResponse
from app.api.v1.customers.service import CustomerService
from app.api.v1.admins.service import AdminService
from app.core.deps import get_db, get_jwt_payload
from app.core.exceptions import AppException

router = APIRouter()


@router.patch(
    "/device-token",
    response_model=UpdateDeviceTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Update device token",
    description="Update device token for push notifications. Works for both customer and admin; use the same JWT you got from login.",
    tags=["auth"],
)
async def update_device_token(
    data: UpdateDeviceTokenRequest,
    payload: dict = Depends(get_jwt_payload),
    db: AsyncSession = Depends(get_db),
):
    """Update device token using JWT. Valid for both customer and admin tokens."""
    sub = payload["sub"]
    role = (payload.get("role") or "").strip().lower()
    token = data.device_token.strip() or None
    if not token:
        AppException().raise_400("device_token cannot be empty")
    try:
        entity_id = UUID(sub)
    except (ValueError, TypeError):
        AppException().raise_401("Invalid token subject")
    if role == "customer":
        customer_service = CustomerService(db)
        await customer_service.update_device_token(entity_id, token)
        return UpdateDeviceTokenResponse(success=True, message="Device token updated")
    if role == "admin":
        admin_service = AdminService(db)
        await admin_service.update_device_token(entity_id, token)
        return UpdateDeviceTokenResponse(success=True, message="Device token updated")
    AppException().raise_401("Unsupported token role for device token update")
