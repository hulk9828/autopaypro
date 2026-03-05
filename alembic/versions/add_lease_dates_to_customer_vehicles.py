"""add lease_start_date and lease_end_date to customer_vehicles; vehicles sold->leased

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-02-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e9f0a1b2c3d4"
down_revision: Union[str, None] = "f0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customer_vehicles",
        sa.Column("lease_start_date", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "customer_vehicles",
        sa.Column("lease_end_date", sa.DateTime(), nullable=True),
    )
    # Normalize existing 'sold' to 'leased' so UI and logic treat all as leased
    op.execute(
        "UPDATE vehicles SET status = 'leased' WHERE status = 'sold'"
    )


def downgrade() -> None:
    op.drop_column("customer_vehicles", "lease_end_date")
    op.drop_column("customer_vehicles", "lease_start_date")
    op.execute(
        "UPDATE vehicles SET status = 'sold' WHERE status = 'leased'"
    )
