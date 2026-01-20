from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.v1.admins.schemas import AdminCreate, AdminLogin
from app.models.admin import Admin
from app.core.security import get_password_hash, verify_password
from app.models.enums import Role


class AdminService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_admin_by_id(self, admin_id: UUID) -> Optional[Admin]:
        result = await self.db.execute(select(Admin).filter(Admin.id == admin_id))
        return result.scalars().first()

    async def get_admin_by_email(self, email: str) -> Optional[Admin]:
        result = await self.db.execute(select(Admin).filter(Admin.email == email))
        return result.scalars().first()

    async def create_admin(self, admin_data: AdminCreate) -> Admin:
        db_admin = await self.get_admin_by_email(admin_data.email)
        if db_admin:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
        
        hashed_password = get_password_hash(admin_data.password)
        new_admin = Admin(
            **admin_data.model_dump(exclude={'password'}), 
            password_hash=hashed_password,
            role=Role.admin.value  # Ensure the role is explicitly set to admin
        )
        self.db.add(new_admin)
        await self.db.commit()
        await self.db.refresh(new_admin)
        return new_admin

    async def authenticate_admin(self, admin_login_data: AdminLogin) -> Optional[Admin]:
        admin = await self.get_admin_by_email(admin_login_data.email)
        if not admin or not verify_password(admin_login_data.password, admin.password_hash):
            return None
        return admin
