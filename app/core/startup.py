"""
Startup utilities for the application.
"""
import logging
from sqlalchemy import select, func, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.core.database import get_async_session_maker_instance
from app.models.admin import Admin
from app.core.security import get_password_hash
from app.models.enums import Role

logger = logging.getLogger(__name__)


async def ensure_admins_table_exists(session):
    """Check if admins table exists."""
    try:
        # Check if table exists by trying to query it
        await session.execute(text("SELECT 1 FROM admins LIMIT 1"))
        return True
    except (ProgrammingError, OperationalError):
        # Table doesn't exist - should be created via Alembic migrations
        logger.warning("Admins table not found. Please run 'alembic upgrade head' to create it.")
        return False


async def ensure_default_admin():
    """
    Check if any admin exists in the database.
    If not, create a default admin with the specified credentials.
    """
    try:
        async_session_maker = get_async_session_maker_instance()
        async with async_session_maker() as session:
            try:
                # First, check if the table exists
                table_exists = await ensure_admins_table_exists(session)
                if not table_exists:
                    logger.warning("Admins table not found. Please run 'alembic upgrade head' to create it.")
                    return
                
                # Check if any admin exists
                result = await session.execute(select(func.count(Admin.id)))
                admin_count = result.scalar()
                
                if admin_count == 0:
                    logger.info("No admin found in database. Creating default admin...")
                    
                    # Create default admin
                    default_email = "autopayadmin@yopmail.com"
                    default_password = "Admin@123"
                    
                    hashed_password = get_password_hash(default_password)
                    default_admin = Admin(
                        email=default_email,
                        password_hash=hashed_password,
                        role=Role.admin.value,
                        is_active=True,
                    )
                    
                    session.add(default_admin)
                    await session.commit()
                    await session.refresh(default_admin)
                    
                    logger.info(
                        f"Default admin created successfully with email: {default_email}"
                    )
                else:
                    logger.info(f"Found {admin_count} admin(s) in database. Skipping default admin creation.")
                    
            except (OperationalError, ProgrammingError) as e:
                logger.warning(
                    f"Database error during admin check/creation. Error: {e}. "
                    f"Please ensure database is accessible and migrations are run."
                )
            except Exception as e:
                logger.error(f"Unexpected error during admin check: {e}", exc_info=True)
                
    except Exception as e:
        logger.error(f"Error during default admin creation: {e}", exc_info=True)
        # Don't raise the exception to allow the application to start
        # The admin can be created manually if needed
