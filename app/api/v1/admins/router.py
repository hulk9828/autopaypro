from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admins.schemas import (
    AdminCreate,
    AdminResponse,
    AdminLogin,
    AdminProfileResponse,
    AdminProfileUpdate,
    AdminChangePassword,
)
from app.api.v1.admins.service import AdminService
from app.core.deps import get_db, get_current_active_admin_user
from app.core.security import create_access_token
from app.core.exceptions import AppException
from datetime import timedelta
from app.core.config import settings
from app.models.user import User

router = APIRouter()


@router.post(
    "/",
    response_model=AdminResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new admin user",
)
async def create_admin(
    admin_data: AdminCreate,
    db: AsyncSession = Depends(get_db),
):
    admin_service = AdminService(db)
    new_admin = await admin_service.create_admin(admin_data)
    return AdminResponse.model_validate(new_admin)


@router.post(
    "/login",
    summary="Admin login",
)
async def admin_login(
    admin_login_data: AdminLogin,
    db: AsyncSession = Depends(get_db),
):
    admin_service = AdminService(db)
    admin = await admin_service.authenticate_admin(admin_login_data)
    if not admin:
        AppException().raise_401("Incorrect email or password")
    if admin_login_data.device_token is not None and admin_login_data.device_token.strip():
        await admin_service.update_device_token(admin.id, admin_login_data.device_token.strip())
        await db.refresh(admin)
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(admin.id),
            "role": admin.role
        },
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer"}


# ============ Admin profile (authenticated admin only) ============

@router.get(
    "/profile",
    response_model=AdminProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get admin profile",
    description="Get current authenticated admin profile.",
    tags=["admin-profile"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def get_admin_profile(
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current admin's profile."""
    service = AdminService(db)
    admin = await service.get_admin_profile(current_admin.id)
    if not admin:
        AppException().raise_404("Admin not found")
    return AdminProfileResponse.model_validate(admin)


@router.patch(
    "/profile",
    response_model=AdminProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update admin profile",
    description="Update current admin profile (email, phone).",
    tags=["admin-profile"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def update_admin_profile(
    data: AdminProfileUpdate,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the current admin's profile. At least one of email or phone can be provided."""
    service = AdminService(db)
    admin = await service.get_admin_profile(current_admin.id)
    if not admin:
        AppException().raise_404("Admin not found")
    updated = await service.update_admin_profile(admin, data)
    return AdminProfileResponse.model_validate(updated)


@router.post(
    "/profile/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change admin password",
    description="Change password for the current authenticated admin.",
    tags=["admin-profile"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def change_admin_password(
    data: AdminChangePassword,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the current admin's password. Requires current password."""
    service = AdminService(db)
    admin = await service.get_admin_profile(current_admin.id)
    if not admin:
        AppException().raise_404("Admin not found")
    await service.change_admin_password(admin, data)
    return {"message": "Password changed successfully"}
