"""add contract number to customer vehicles

Revision ID: contract_no_001
Revises: checkout_001
Create Date: 2026-03-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "contract_no_001"
down_revision: Union[str, None] = "checkout_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customer_vehicles",
        sa.Column("contract_number", sa.String(length=100), nullable=True),
    )
    op.create_index(
        "ux_customer_vehicles_contract_number",
        "customer_vehicles",
        ["contract_number"],
        unique=True,
        postgresql_where=sa.text("contract_number IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_customer_vehicles_contract_number", table_name="customer_vehicles")
    op.drop_column("customer_vehicles", "contract_number")
