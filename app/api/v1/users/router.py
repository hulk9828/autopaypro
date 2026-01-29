from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.users.schemas import UserCreate, UserResponse, UserUpdate
from app.api.v1.users.service import UserService
from app.core.deps import get_db, get_current_active_admin_user
from app.core.exceptions import AppException
from app.models.enums import Role


router = APIRouter()


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
    dependencies=[Depends(get_current_active_admin_user)],
)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    user_service = UserService(db)
    new_user = await user_service.create_user(user_data)
    return UserResponse.from_orm(new_user)


@router.get(
    "/",
    response_model=List[UserResponse],
    summary="Get all users",
    dependencies=[Depends(get_current_active_admin_user)],
)
async def get_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    user_service = UserService(db)
    users = await user_service.get_users(skip=skip, limit=limit)
    return [UserResponse.from_orm(user) for user in users]


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get a user by ID",
    dependencies=[Depends(get_current_active_admin_user)],
)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    user_service = UserService(db)
    user = await user_service.get_user_by_id(user_id)
    if not user:
        AppException().raise_404("User not found")
    return UserResponse.from_orm(user)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update a user by ID",
    dependencies=[Depends(get_current_active_admin_user)],
)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
):
    user_service = UserService(db)
    updated_user = await user_service.update_user(user_id, user_data)
    if not updated_user:
        AppException().raise_404("User not found")
    return UserResponse.from_orm(updated_user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user by ID",
    dependencies=[Depends(get_current_active_admin_user)],
)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    user_service = UserService(db)
    deleted = await user_service.delete_user(user_id)
    if not deleted:
        AppException().raise_404("User not found")
    return None
