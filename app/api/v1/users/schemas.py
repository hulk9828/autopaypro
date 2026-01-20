from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import Role


class UserBase(BaseModel):
    email: EmailStr
    phone: Optional[str] = None
    role: Role = Role.user # Default role is user
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(UserBase):
    email: Optional[EmailStr] = None
    role: Optional[Role] = None
    is_active: Optional[bool] = None


class UserInDB(UserBase):
    id: UUID
    password_hash: str

    class Config:
        from_attributes = True


class UserResponse(UserBase):
    id: UUID

    class Config:
        from_attributes = True
