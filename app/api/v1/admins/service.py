from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.v1.admins.schemas import AdminCreate, AdminLogin, AdminProfileUpdate, AdminChangePassword
from app.core.exceptions import AppException
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
            AppException().raise_400("Email already registered")
        
        hashed_password = get_password_hash(admin_data.password)
        new_admin = Admin(
            **admin_data.model_dump(exclude={'password', 'role'}), 
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

    async def get_admin_profile(self, admin_id: UUID) -> Optional[Admin]:
        """Get admin by ID for profile (same as get_admin_by_id)."""
        return await self.get_admin_by_id(admin_id)

    async def update_admin_profile(self, admin: Admin, data: AdminProfileUpdate) -> Admin:
        """Update admin email and/or phone. Validates uniqueness."""
        if data.email is not None and data.email != admin.email:
            existing = await self.get_admin_by_email(data.email)
            if existing:
                AppException().raise_400("Email already registered")
            admin.email = data.email
        if data.phone is not None:
            if data.phone.strip() == "":
                admin.phone = None
            else:
                result = await self.db.execute(select(Admin).where(Admin.phone == data.phone.strip()).where(Admin.id != admin.id))
                if result.scalars().first():
                    AppException().raise_400("Phone already registered")
                admin.phone = data.phone.strip()
        if data.profile_pic is not None:
            admin.profile_pic = data.profile_pic.strip() or None
        self.db.add(admin)
        await self.db.commit()
        await self.db.refresh(admin)
        return admin

    async def change_admin_password(self, admin: Admin, data: AdminChangePassword) -> None:
        """Change admin password. Verifies current password."""
        if not verify_password(data.current_password, admin.password_hash):
            AppException().raise_400("Current password is incorrect")
        admin.password_hash = get_password_hash(data.new_password)
        self.db.add(admin)
        await self.db.commit()
