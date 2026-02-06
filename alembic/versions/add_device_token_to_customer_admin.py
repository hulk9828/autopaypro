"""add device_token to customer and admin

Revision ID: f7g8h9i0j1k2
Revises: 4ea40789475c
Create Date: 2026-02-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7g8h9i0j1k2"
down_revision: Union[str, None] = "4ea40789475c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("device_token", sa.String(), nullable=True))
    op.add_column("admins", sa.Column("device_token", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("admins", "device_token")
    op.drop_column("customers", "device_token")
