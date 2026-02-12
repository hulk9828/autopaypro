from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import Role


class AdminBase(BaseModel):
    email: EmailStr
    phone: Optional[str] = None
    role: Role = Role.admin # Default role is admin
    is_active: bool = True


class AdminCreate(AdminBase):
    password: str = Field(..., min_length=8)


class AdminUpdate(AdminBase):
    email: Optional[EmailStr] = None
    role: Optional[Role] = None
    is_active: Optional[bool] = None


class AdminProfileResponse(BaseModel):
    """Admin profile for GET (no sensitive data)."""
    id: UUID
    email: str
    phone: Optional[str] = None
    profile_pic: Optional[str] = None
    role: str
    is_active: bool
    device_token: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AdminProfileUpdate(BaseModel):
    """Update admin profile (email, phone, profile_pic, device_token)."""
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    profile_pic: Optional[str] = None
    device_token: Optional[str] = None


class AdminChangePassword(BaseModel):
    """Change password for current admin."""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


class AdminInDB(AdminBase):
    id: UUID
    password_hash: str

    class Config:
        from_attributes = True


class AdminResponse(AdminBase):
    id: UUID

    class Config:
        from_attributes = True


class AdminLogin(BaseModel):
    email: EmailStr
    password: str
    device_token: Optional[str] = None


class AdminForgotPassword(BaseModel):
    """Request password reset; sends reset link/OTP to admin email."""
    email: EmailStr


class AdminResetPassword(BaseModel):
    """Reset password using the token received via email."""
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)