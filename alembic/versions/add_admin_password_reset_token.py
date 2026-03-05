"""add admin password_reset_token and password_reset_token_expires_at

Revision ID: admin_reset_001
Revises: merge_lease_001
Create Date: 2026-02-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "admin_reset_001"
down_revision: Union[str, None] = "merge_lease_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admins",
        sa.Column("password_reset_token", sa.String(), nullable=True),
    )
    op.add_column(
        "admins",
        sa.Column("password_reset_token_expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        op.f("ix_admins_password_reset_token"),
        "admins",
        ["password_reset_token"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_admins_password_reset_token"), table_name="admins")
    op.drop_column("admins", "password_reset_token_expires_at")
    op.drop_column("admins", "password_reset_token")
