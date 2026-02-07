"""add note column to payments

Revision ID: c9d0e1f2g3h4
Revises: a8b9c0d1e2f3
Create Date: 2026-02-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d0e1f2g3h4"
down_revision: Union[str, None] = "96f3b0cbdc8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("note", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payments", "note")
