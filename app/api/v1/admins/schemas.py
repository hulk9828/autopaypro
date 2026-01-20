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