import asyncio
import os
from pathlib import Path
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import pool, create_engine
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# -------------------------------------------------
# Load .env explicitly (ABSOLUTE PATH)
# -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Check your .env file.")

print("ALEMBIC DATABASE_URL:", DATABASE_URL)

# -------------------------------------------------
# Alembic config
# -------------------------------------------------

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the database URL in the config for autogenerate operations
# Convert async URL to sync URL for version checking (autogenerate needs this)
SYNC_DATABASE_URL = DATABASE_URL.replace("+asyncpg", "").replace("postgresql+asyncpg://", "postgresql://")
config.set_main_option("sqlalchemy.url", SYNC_DATABASE_URL)

# -------------------------------------------------
# Import models AFTER env is loaded
# -------------------------------------------------

from app.core.database import Base  # noqa
from app.models.user import User  # noqa
from app.models.vehicle import Vehicle  # noqa
from app.models.customer import Customer  # noqa
from app.models.customer_vehicle import CustomerVehicle  # noqa
from app.models.admin import Admin  # admin
from app.models.loan import Loan  # noqa

target_metadata = Base.metadata

# -------------------------------------------------
# Offline migrations
# -------------------------------------------------

def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()

# -------------------------------------------------
# Online migrations (ASYNC SAFE)
# -------------------------------------------------

def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    # Use async engine for migrations
    engine = async_engine_from_config(
        {
            "sqlalchemy.url": DATABASE_URL
        },
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await engine.dispose()

# -------------------------------------------------
# Entrypoint
# -------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
