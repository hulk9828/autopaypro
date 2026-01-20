import os

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

from app.core.config import settings


def get_database_url():
    db_url = settings.DATABASE_URL
    if "postgresql" in db_url and "sslmode" not in db_url and settings.ENVIRONMENT != "development":
        return f"{db_url}?sslmode=require"
    return db_url


DATABASE_URL = get_database_url()
engine = create_async_engine(DATABASE_URL, echo=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()


def get_async_session_maker_instance():
    """Get the async session maker instance."""
    return async_session_maker


async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        yield session
