"""add status column to loans

Revision ID: d8e9f0a1b2c3
Revises: c9d0e1f2g3h4
Create Date: 2026-02-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, None] = "c9d0e1f2g3h4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE loans ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active' NOT NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE loans DROP COLUMN IF EXISTS status")
