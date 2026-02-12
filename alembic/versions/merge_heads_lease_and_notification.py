"""merge heads: payment_notification_log and lease/vehicles branch

Revision ID: merge_lease_001
Revises: a8b9c0d1e2f3, v1leaseprice001
Create Date: 2026-02-11

"""
from typing import Sequence, Union

from alembic import op


revision: str = "merge_lease_001"
down_revision: Union[str, None] = ("a8b9c0d1e2f3", "v1leaseprice001")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
