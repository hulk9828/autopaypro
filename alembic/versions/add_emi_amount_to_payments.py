"""add emi_amount to payments

Revision ID: emi_amount_001
Revises: lease_end_001
Create Date: 2026-02-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "emi_amount_001"
down_revision: Union[str, None] = "lease_end_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("emi_amount", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payments", "emi_amount")
