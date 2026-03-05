from typing import Optional

from fastapi import APIRouter, Depends, File, Form, status, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admins.schemas import (
    AdminCreate,
    AdminResponse,
    AdminLogin,
    AdminForgotPassword,
    AdminVerifyOtp,
    AdminResetPassword,
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


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    summary="Admin forgot password",
    description="Send a 6-digit OTP to admin email. Always returns success to avoid email enumeration.",
)
async def admin_forgot_password(
    data: AdminForgotPassword,
    db: AsyncSession = Depends(get_db),
):
    admin_service = AdminService(db)
    await admin_service.request_password_reset(data.email)
    return {"message": "If an account exists with this email, an OTP has been sent."}


@router.post(
    "/verify-otp",
    status_code=status.HTTP_200_OK,
    summary="Verify OTP",
    description="Verify the 6-digit OTP sent to admin email. Call before reset-password.",
)
async def admin_verify_otp(
    data: AdminVerifyOtp,
    db: AsyncSession = Depends(get_db),
):
    admin_service = AdminService(db)
    await admin_service.verify_otp(data.email, data.otp)
    return {"message": "OTP verified successfully."}


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Admin reset password",
    description="Reset password using email, OTP (from email), and new password.",
)
async def admin_reset_password(
    data: AdminResetPassword,
    db: AsyncSession = Depends(get_db),
):
    admin_service = AdminService(db)
    await admin_service.reset_password_with_otp(data.email, data.otp, data.new_password)
    return {"message": "Password has been reset successfully. You can now log in with your new password."}


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
    description="Update current admin profile via multipart/form-data. Optional: email, phone, device_token; optional profile_pic = image file (uploaded to S3, URL saved on admin).",
    tags=["admin-profile"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def update_admin_profile(
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    device_token: Optional[str] = Form(None),
    profile_pic: Optional[UploadFile] = File(None, description="Profile image (JPEG, PNG, WebP, GIF). Uploaded to S3; URL saved on admin."),
):
    """Update the current admin's profile. Send as multipart/form-data. Optional text fields + optional profile image file."""
    service = AdminService(db)
    admin = await service.get_admin_profile(current_admin.id)
    if not admin:
        AppException().raise_404("Admin not found")
    data = AdminProfileUpdate(
        email=email,
        phone=phone,
        device_token=device_token,
        profile_pic=None,
    )
    updated = await service.update_admin_profile(admin, data)
    if profile_pic and profile_pic.filename:
        if not profile_pic.content_type or not profile_pic.content_type.startswith("image/"):
            AppException().raise_400("Profile image must be an image (JPEG, PNG, WebP, or GIF)")
        content = await profile_pic.read()
        if not content:
            AppException().raise_400("Profile image file is empty")
        updated = await service.upload_profile_photo(updated, content, profile_pic.content_type)
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
