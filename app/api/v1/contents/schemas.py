from typing import Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field


class ContentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Content title")
    description: Optional[str] = Field(None, description="Content description")
    keyword: str = Field(..., min_length=1, max_length=255, description="Keyword to categorize and fetch content")


class ContentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    keyword: Optional[str] = Field(None, min_length=1, max_length=255)


class ContentResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    keyword: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
