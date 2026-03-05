"""add total_paid to loans; payment_mode and applied_installments to payments

Revision ID: flexible_pay_001
Revises: emi_amount_001
Create Date: 2026-02-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


revision: str = "flexible_pay_001"
down_revision: Union[str, None] = "emi_amount_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "loans",
        sa.Column("total_paid", sa.Float(), nullable=False, server_default="0"),
    )
    # Backfill total_paid from existing payments, then reduce amount_financed
    op.execute("""
        UPDATE loans l
        SET total_paid = COALESCE((
            SELECT SUM(p.amount) FROM payments p
            WHERE p.loan_id = l.id AND p.status = 'completed'
        ), 0)
    """)
    op.execute("""
        UPDATE loans l
        SET amount_financed = GREATEST(0, l.amount_financed - l.total_paid)
    """)
    op.execute("""
        UPDATE loans SET status = 'closed' WHERE amount_financed <= 0 AND status != 'closed'
    """)
    op.add_column(
        "payments",
        sa.Column("payment_mode", sa.String(20), nullable=True),
    )
    op.add_column(
        "payments",
        sa.Column("applied_installments", JSON, nullable=True),
    )
    # Backfill payment_mode for existing records
    op.execute(
        "UPDATE payments SET payment_mode = 'installment' WHERE payment_mode IS NULL"
    )
    op.alter_column(
        "payments",
        "payment_mode",
        nullable=False,
        server_default="installment",
    )


def downgrade() -> None:
    op.drop_column("payments", "applied_installments")
    op.drop_column("payments", "payment_mode")
    op.drop_column("loans", "total_paid")
