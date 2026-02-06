"""add payment status column

Revision ID: e1f2a3b4c5d6
Revises: 738c0bc5fbf6
Create Date: 2026-02-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "738c0bc5fbf6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("status", sa.String(20), nullable=False, server_default="completed"),
    )


def downgrade() -> None:
    op.drop_column("payments", "status")
