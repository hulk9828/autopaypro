"""add payment_notification_logs table

Revision ID: a8b9c0d1e2f3
Revises: 4ea40789475c
Create Date: 2026-02-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, None] = "4ea40789475c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_notification_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("scope_key", sa.String(255), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("notification_type", "scope_key", name="uq_notification_type_scope_key"),
    )
    op.create_index("ix_payment_notification_logs_scope_key", "payment_notification_logs", ["scope_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_payment_notification_logs_scope_key", table_name="payment_notification_logs")
    op.drop_table("payment_notification_logs")
