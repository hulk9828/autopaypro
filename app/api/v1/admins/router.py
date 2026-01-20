from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admins.schemas import AdminCreate, AdminResponse, AdminLogin
from app.api.v1.admins.service import AdminService
from app.core.deps import get_db, get_current_active_admin_user
from app.core.security import create_access_token
from datetime import timedelta
from app.core.config import settings

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
    return AdminResponse.from_orm(new_admin)


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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(admin.id),
            "role": admin.role
        },
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer"}
