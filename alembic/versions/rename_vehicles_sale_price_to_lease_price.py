"""rename vehicles.sale_price to lease_price

Revision ID: a1b2c3d4e5f6
Revises: f0a1b2c3d4e5
Create Date: 2026-02-09

"""
from typing import Sequence, Union

from alembic import op


revision: str = "v1leaseprice001"
down_revision: Union[str, None] = "e9f0a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "vehicles",
        "sale_price",
        new_column_name="lease_price",
    )


def downgrade() -> None:
    op.alter_column(
        "vehicles",
        "lease_price",
        new_column_name="sale_price",
    )
