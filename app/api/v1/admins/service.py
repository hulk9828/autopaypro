import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.v1.admins.schemas import AdminCreate, AdminLogin, AdminProfileUpdate, AdminChangePassword
from app.core.exceptions import AppException
from app.core import s3 as s3_module
from app.core import email as email_module
from app.models.admin import Admin
from app.core.security import get_password_hash, verify_password, create_password_reset_otp
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

    async def update_device_token(self, admin_id: UUID, device_token: str) -> None:
        """Update device token for push notifications."""
        admin = await self.get_admin_by_id(admin_id)
        if admin:
            admin.device_token = device_token or None
            self.db.add(admin)
            await self.db.commit()

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
        if data.device_token is not None:
            admin.device_token = data.device_token.strip() or None
        self.db.add(admin)
        await self.db.commit()
        await self.db.refresh(admin)
        return admin

    async def upload_profile_photo(self, admin: Admin, file_content: bytes, content_type: str) -> Admin:
        """Upload profile photo to S3 and set admin.profile_pic to the URL."""
        url = await asyncio.to_thread(
            s3_module.upload_admin_profile_photo,
            file_content,
            str(admin.id),
            content_type,
        )
        admin.profile_pic = url
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

    async def request_password_reset(self, email: str) -> None:
        """
        Generate a 6-digit OTP for the admin, store it with expiry (10 min), and send OTP to email.
        Does not reveal whether the email exists (always return success for security).
        """
        admin = await self.get_admin_by_email(email)
        if not admin:
            return
        otp = create_password_reset_otp()
        # Use naive UTC for TIMESTAMP WITHOUT TIME ZONE (asyncpg rejects aware datetimes). OTP valid 10 min.
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).replace(tzinfo=None)
        admin.password_reset_token = otp
        admin.password_reset_token_expires_at = expires_at
        self.db.add(admin)
        await self.db.commit()

        await email_module.send_admin_password_reset_otp_email(
            admin_email=admin.email,
            otp_code=otp,
        )

    async def verify_otp(self, email: str, otp: str) -> None:
        """Verify OTP for the given admin email. Raises if invalid or expired."""
        admin = await self.get_admin_by_email(email)
        if not admin:
            AppException().raise_400("Invalid or expired OTP")
        now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        if (
            admin.password_reset_token != otp
            or admin.password_reset_token_expires_at is None
            or admin.password_reset_token_expires_at <= now_utc_naive
        ):
            AppException().raise_400("Invalid or expired OTP")

    async def reset_password_with_otp(self, email: str, otp: str, new_password: str) -> None:
        """Verify OTP for email, then set new password and clear OTP."""
        admin = await self.get_admin_by_email(email)
        if not admin:
            AppException().raise_400("Invalid or expired OTP")
        now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        if (
            admin.password_reset_token != otp
            or admin.password_reset_token_expires_at is None
            or admin.password_reset_token_expires_at <= now_utc_naive
        ):
            AppException().raise_400("Invalid or expired OTP")
        admin.password_hash = get_password_hash(new_password)
        admin.password_reset_token = None
        admin.password_reset_token_expires_at = None
        self.db.add(admin)
        await self.db.commit()
