"""add lease_payment_type to loans; interest_rate nullable

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-02-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, None] = "d8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE loans ADD COLUMN IF NOT EXISTS lease_payment_type VARCHAR(20) DEFAULT 'bi_weekly' NOT NULL"
    )
    op.alter_column(
        "loans",
        "interest_rate",
        existing_type=sa.Float(),
        nullable=True,
    )


def downgrade() -> None:
    op.drop_column("loans", "lease_payment_type")
    op.execute("UPDATE loans SET interest_rate = 0 WHERE interest_rate IS NULL")
    op.alter_column(
        "loans",
        "interest_rate",
        existing_type=sa.Float(),
        nullable=False,
    )
