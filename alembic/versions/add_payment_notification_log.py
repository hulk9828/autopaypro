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
    op.execute("""
        CREATE TABLE IF NOT EXISTS payment_notification_logs (
            id UUID NOT NULL,
            notification_type VARCHAR(50) NOT NULL,
            scope_key VARCHAR(255) NOT NULL,
            customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            sent_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_notification_type_scope_key UNIQUE (notification_type, scope_key)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_payment_notification_logs_scope_key ON payment_notification_logs (scope_key)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_payment_notification_logs_scope_key")
    op.execute("DROP TABLE IF EXISTS payment_notification_logs")
