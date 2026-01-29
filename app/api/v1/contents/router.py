from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.contents.schemas import ContentCreate, ContentUpdate, ContentResponse
from app.api.v1.contents.service import ContentService
from app.core.deps import get_db, get_current_active_admin_user
from app.models.user import User

router = APIRouter()


@router.post(
    "/",
    response_model=ContentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create content",
    description="Create new content with title, description, and keyword. Admin only.",
    tags=["content"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def create_content(
    data: ContentCreate,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = ContentService(db)
    content = await service.create_content(data)
    return ContentResponse.model_validate(content)


@router.get(
    "/",
    response_model=List[ContentResponse],
    summary="List content",
    description="List all content with optional keyword filter.",
    tags=["content"],
)
async def get_contents(
    keyword: Optional[str] = Query(None, description="Filter by keyword (searches keyword, title, description)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    service = ContentService(db)
    contents = await service.get_contents(keyword=keyword, skip=skip, limit=limit)
    return [ContentResponse.model_validate(c) for c in contents]


@router.get(
    "/by-keyword",
    response_model=ContentResponse,
    summary="Fetch one content by keyword",
    description="Fetch the first content matching the given keyword. Searches in keyword, title, and description. Returns 404 if none found.",
    tags=["content"],
)
async def fetch_content_by_keyword(
    keyword: str = Query(..., min_length=1, description="Keyword to search (keyword, title, description)"),
    db: AsyncSession = Depends(get_db),
):
    from app.core.exceptions import AppException
    service = ContentService(db)
    content = await service.get_content_by_keyword(keyword=keyword)
    if not content:
        AppException().raise_404("No content found for this keyword")
    return ContentResponse.model_validate(content)


@router.get(
    "/{content_id}",
    response_model=ContentResponse,
    summary="Get content by ID",
    tags=["content"],
)
async def get_content(
    content_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    service = ContentService(db)
    content = await service.get_content_by_id(content_id)
    if not content:
        from app.core.exceptions import AppException
        AppException().raise_404("Content not found")
    return ContentResponse.model_validate(content)


@router.patch(
    "/{content_id}",
    response_model=ContentResponse,
    summary="Update content",
    description="Update content. Admin only.",
    tags=["content"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def update_content(
    content_id: UUID,
    data: ContentUpdate,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = ContentService(db)
    content = await service.update_content(content_id, data)
    return ContentResponse.model_validate(content)


@router.delete(
    "/{content_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete content",
    description="Delete content. Admin only.",
    tags=["content"],
    dependencies=[Depends(get_current_active_admin_user)],
)
async def delete_content(
    content_id: UUID,
    current_admin: User = Depends(get_current_active_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = ContentService(db)
    await service.delete_content(content_id)
