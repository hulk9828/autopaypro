"""add lease_end_date to vehicles

Revision ID: lease_end_001
Revises: admin_reset_001
Create Date: 2026-02-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "lease_end_001"
down_revision: Union[str, None] = "admin_reset_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "vehicles",
        sa.Column("lease_end_date", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("vehicles", "lease_end_date")
