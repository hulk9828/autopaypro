from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.api.v1.contents.schemas import ContentCreate, ContentUpdate
from app.core.exceptions import AppException
from app.models.content import Content


class ContentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_content(self, data: ContentCreate) -> Content:
        content = Content(
            title=data.title,
            description=data.description,
            keyword=data.keyword.strip().lower(),
        )
        self.db.add(content)
        await self.db.commit()
        await self.db.refresh(content)
        return content

    async def get_content_by_id(self, content_id: UUID) -> Optional[Content]:
        return await self.db.get(Content, content_id)

    async def get_contents(
        self,
        keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Content]:
        query = select(Content).order_by(Content.created_at.desc())
        if keyword and keyword.strip():
            term = f"%{keyword.strip().lower()}%"
            query = query.where(
                or_(
                    Content.keyword.ilike(term),
                    Content.title.ilike(term),
                    Content.description.ilike(term),
                )
            )
        result = await self.db.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def update_content(self, content_id: UUID, data: ContentUpdate) -> Content:
        content = await self.get_content_by_id(content_id)
        if not content:
            AppException().raise_404("Content not found")
        if data.title is not None:
            content.title = data.title
        if data.description is not None:
            content.description = data.description
        if data.keyword is not None:
            content.keyword = data.keyword.strip().lower()
        self.db.add(content)
        await self.db.commit()
        await self.db.refresh(content)
        return content

    async def delete_content(self, content_id: UUID) -> None:
        content = await self.get_content_by_id(content_id)
        if not content:
            AppException().raise_404("Content not found")
        await self.db.delete(content)
        await self.db.commit()
