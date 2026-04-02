from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import get_async_session_maker_instance

router = APIRouter()


@router.get("/", summary="Health Check")
async def health_check():
    return {"status": "ok"}


async def is_database_connected() -> bool:
    """Return True if DB accepts a simple SELECT 1 query."""
    async_session_maker = get_async_session_maker_instance()
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@router.get("/db", summary="Database Health Check")
async def database_health_check():
    connected = await is_database_connected()
    return {
        "database_connected": connected,
        "status": "ok" if connected else "not_connected",
    }
