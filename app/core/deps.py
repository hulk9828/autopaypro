from typing import AsyncGenerator
from uuid import UUID

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import async_session_maker
from app.core.security import decode_access_token
from app.core.exceptions import AppException
from app.models.user import User
from app.models.admin import Admin
from app.models.customer import Customer
from app.models.enums import Role, AccountStatus


bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    """
    Get current user from JWT token.
    Handles both User and Admin models by checking the role in the token.
    Returns a User object (for admins, creates a temporary User-like object or checks Admin table).
    """
    if credentials is None or not credentials.credentials:
        AppException().raise_401("Not authenticated")
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        AppException().raise_401("Could not validate credentials")
    
    user_id: str = payload.get("sub")
    role: str = payload.get("role")
    
    if user_id is None:
        AppException().raise_401("Could not validate credentials")
    
    # If role is admin, check Admin table
    if role and role == Role.admin.value:
        admin = await db.get(Admin, UUID(user_id))
        if admin is None:
            AppException().raise_401("Could not validate credentials")
        if not admin.is_active:
            AppException().raise_401("Admin account is inactive")
        # Create a User-like object from Admin for compatibility
        # We'll create a temporary User object with admin data
        user = User(
            id=admin.id,
            email=admin.email,
            phone=admin.phone,
            password_hash=admin.password_hash,
            role=admin.role,
            is_active=admin.is_active,
            created_at=admin.created_at,
            updated_at=admin.updated_at
        )
        return user
    
    # Otherwise, check User table
    user = await db.get(User, UUID(user_id))
    if user is None:
        AppException().raise_401("Could not validate credentials")
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        AppException().raise_400("Inactive user")
    return current_user


async def get_current_active_admin_user(current_user: User = Depends(get_current_active_user)) -> User:
    if current_user.role != Role.admin.value:
        AppException().raise_403("Not an admin user")
    return current_user


async def get_current_customer(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Customer:
    """Get the current authenticated customer from JWT token."""
    if credentials is None or not credentials.credentials:
        AppException().raise_401("Not authenticated. Please provide a bearer token.")
    
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        AppException().raise_401("Invalid or expired token. Please login again.")
    
    # Check if the token is for a customer
    role = payload.get("role")
    if not role:
        AppException().raise_401("Token missing role. Please login as a customer.")
    
    if role != "customer":
        AppException().raise_401(f"Invalid token type. Expected 'customer' role, got '{role}'. Please use a customer login token.")
    
    customer_id: str = payload.get("sub")
    if customer_id is None:
        AppException().raise_401("Token missing customer ID. Please login again.")
    
    try:
        customer_uuid = UUID(customer_id)
    except (ValueError, TypeError):
        AppException().raise_401("Invalid customer ID format in token.")
    
    customer = await db.get(Customer, customer_uuid)
    if customer is None:
        AppException().raise_401("Customer not found. Please login again.")
    
    # Check if account is active
    if customer.account_status != AccountStatus.active.value:
        AppException().raise_403("Customer account is inactive. Please contact support.")
    
    return customer
